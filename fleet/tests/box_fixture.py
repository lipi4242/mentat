"""Hermetikus box a `fleet box-upgrade` tesztjeihez.

Valódi git (helyi „publikus repó" v1 és v2 taggel), hamis `systemctl` (fakebin),
és a checkoutban egy hamis `fleet/bin/fleet`, ami a hívásait a `calls` naplóba
írja `fleet[<verzió>] …` alakban — így látszik, MELYIK kód futott. Hibát a
`$FAKE_DIR/fail-<verzió>-<mi>` fájllal lehet injektálni.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
import time
from pathlib import Path

from fakebin import FakeBin
from fleet import registry
from fleet.box_ctx import Ctx

FAKE_FLEET = r'''#!/bin/sh
H="$(cd "$(dirname "$0")/.." && pwd -P)"; V="$(cat "$H/FAKEVER")"
echo "fleet[$V] $*" >> "$FAKE_DIR/calls"
f() { [ -e "$FAKE_DIR/fail-$V-$1" ]; }
case "$1" in
  --version) echo "fleet $V";;
  release) f release && { echo nem-json; exit 0; }; printf '{"sha": "%s"}\n' "$(git -C "$H" rev-parse --short HEAD)";;
  render) f "render-$2" && { echo "render bukott" >&2; exit 1; }; printf '[Service]\n# %s %s\n' "$2" "$V";;
  install) f "killed-$2" && kill -INT $$; f "hup-parent-$2" && kill -HUP $PPID
           f "install-$2" && { echo "install bukott: $2"; exit 1; }; f "ipending-$2" && exit 3; exit 0;;
  bridge) f "bridge-$2-$3" && exit 1
          if [ "$2" = install ]; then echo "# új híd-unit" > "$BOX_HOME/.config/systemd/user/$3-telegram-bridge.service"
            f "bridge-early-$3" && exit 1   # a .bak előtt bukik
            # mint a copy_bridge: a régi .bak-<idő> alá, az új a helyére
            D="$BOX_HOME/.config/$3"; [ -d "$D/sub-etha" ] && mv "$D/sub-etha" "$D/sub-etha.bak-$(date +%Y%m%d-%H%M%S)"
            f "bridge-half-$3" && exit 1; cp -R "$H/bridge" "$D/sub-etha"; fi; exit 0;;
  postcheck) f "postcheck-$2" && { echo "postcheck $2: FAILED (0 s várva)"; exit 1; }
             f "pending-$2" && { echo "postcheck $2: PENDING (0 s várva)"; exit 1; }; exit 0;;
  reconcile) cat "$FAKE_DIR/observe-$V" 2>/dev/null; exit 0;;
  doctor) echo "doctor $V";;
esac
exit 0
'''
DROPIN_TMPL = "[Service]\nExecStartPre=-@@FLEET_ROOT@@/bin/agent-session-gate.sh @@AGENT@@\n"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "init.defaultBranch=main"]


def git(repo: Path, *args: str) -> str:
    return subprocess.run([*GIT, "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _fleet_tree(root: Path, ver: str, bridge: str) -> None:
    (root / "bin").mkdir(parents=True, exist_ok=True)
    (root / "bin" / "fleet").write_text(FAKE_FLEET)
    (root / "bin" / "fleet").chmod(0o755)
    (root / "FAKEVER").write_text(ver + "\n")
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "10-session-gate.conf.tmpl").write_text(DROPIN_TMPL)
    b = root / "bridge"
    (b / "lib").mkdir(parents=True, exist_ok=True)
    for n in ("bridge.mjs", "send.mjs", "delivery.mjs", "lib/x.mjs"):
        (b / n).write_text(f"// {n} {bridge}\n")
    (b / "VERSION").write_text(bridge + "\n")


class Box:
    def __init__(self, agents=("a", "b")):
        self._tmp = tempfile.TemporaryDirectory()
        t = Path(self._tmp.name)
        self.fb = FakeBin()
        for tm in ("fleet-reconcile.timer", "fleet-reconcile-fast.timer"):
            self.fb.set_active(tm)
        self.home, self.origin = t / "home", t / "origin"
        self.home.mkdir()
        self._saved_maint = os.environ.get("FLEET_MAINTENANCE_DIR")
        os.environ["FLEET_MAINTENANCE_DIR"] = str(t / "maint")
        self._saved_bh = os.environ.get("BOX_HOME")
        os.environ["BOX_HOME"] = str(self.home)
        subprocess.run([*GIT, "init", "-q", str(self.origin)], check=True)
        for ver, br in (("v1", "2.0.1"), ("v2", "2.1.0")):
            _fleet_tree(self.origin / "fleet", ver, br)
            git(self.origin, "add", "-A"); git(self.origin, "commit", "-qm", ver); git(self.origin, "tag", ver)
        self.sha = {v: git(self.origin, "rev-parse", f"{v}^{{commit}}") for v in ("v1", "v2")}
        self.entries = [registry.normalize({"agent": n, "workdir": f"/w/{n}", "host": "box1"}) for n in agents]
        self.units = self.home / ".config" / "systemd" / "user"
        self.units.mkdir(parents=True)
        self.out: list[str] = []

    # ── elrendezések ──────────────────────────────────────────────────────
    def legacy(self) -> None:
        leg = self.home / "fleet-leader"
        _fleet_tree(leg, "legacy", "2.0.1")
        subprocess.run([*GIT, "init", "-q", str(leg)], check=True)
        git(leg, "add", "-A"); git(leg, "commit", "-qm", "legacy")

    def symlink_at(self, tag: str) -> None:
        src = self.home / "src" / "mentat"
        src.parent.mkdir(parents=True)
        subprocess.run([*GIT, "clone", "-q", str(self.origin), str(src)], check=True)
        git(src, "-c", "advice.detachedHead=false", "checkout", "-q", tag)
        os.symlink(src / "fleet", self.home / "fleet-leader")

    # ── ágens-állapot ─────────────────────────────────────────────────────
    def unit_as(self, agent: str, ver: str, dropin: bool = True) -> None:
        (self.units / f"{agent}.service").write_text(f"[Service]\n# {agent} {ver}\n")
        if dropin:
            d = self.units / f"{agent}.service.d"
            d.mkdir(exist_ok=True)
            (d / "10-session-gate.conf").write_text(
                DROPIN_TMPL.replace("@@AGENT@@", agent).replace("@@FLEET_ROOT@@", "%h/src/mentat/fleet"))

    def bridge_as(self, agent: str, ver: str) -> None:
        """Telepített híd a `ver` verzió fájljaival (a v1 = 2.0.1, a v2 = 2.1.0)."""
        tree = self.home / "tmp-br"
        _fleet_tree(tree, "x", ver)
        (self.home / ".config" / agent).mkdir(parents=True, exist_ok=True)
        os.rename(tree / "bridge", self.home / ".config" / agent / "sub-etha")

    def busy(self, agent: str) -> None:
        (self.home / ".config" / agent).mkdir(parents=True, exist_ok=True)
        (self.home / ".config" / agent / "session.id").write_text("sid-" + agent)
        p = self.home / ".claude" / "projects" / "w" / f"sid-{agent}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n")
        os.utime(p, (time.time(), time.time()))

    def fail(self, what: str) -> None:
        (self.fb.dir / f"fail-{what}").touch()

    def ctx(self, tag: str = "v2", **kw) -> Ctx:
        c = Ctx(home=self.home, tag=tag, url=str(self.origin), say=self.out.append,
                sleep=lambda s: None, **kw)
        c.state["registry_agents"] = self.entries
        return c

    @staticmethod
    def raise_once(ctx: Ctx, match, exc: BaseException, after: bool = False) -> None:
        """A `match(cmd)`-re illő ELSŐ hívás helyett (after=True: a hívás UTÁN) `exc` —
        Ctrl-C / megszakadt ssh a hívás közben, vagy rögtön utána."""
        orig, fired = ctx.run, []

        def run(cmd):
            if not fired and match([str(c) for c in cmd]):
                fired.append(cmd)
                if after:
                    orig(cmd)
                raise exc
            return orig(cmd)
        ctx.run = run

    def head(self) -> str:
        return git(self.home / "src" / "mentat", "rev-parse", "HEAD")

    def calls(self) -> list[str]:
        return self.fb.calls()

    def cleanup(self) -> None:
        if self._saved_maint is None:
            os.environ.pop("FLEET_MAINTENANCE_DIR", None)
        else:
            os.environ["FLEET_MAINTENANCE_DIR"] = self._saved_maint
        os.environ.pop("BOX_HOME", None) if self._saved_bh is None else os.environ.update(BOX_HOME=self._saved_bh)
        self.fb.cleanup()
        self._tmp.cleanup()
