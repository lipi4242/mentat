#!/usr/bin/env python3
"""Upgrade a Mentat brain in place to the release next to this tool (UPGRADE.md, step 3).

    python3 -I .mentat/bin/mentat_upgrade.py inventory [--repo .]
    python3 -I .mentat/bin/mentat_upgrade.py plan --lang hu|en [--agent NAME]
    python3 -I .mentat/bin/mentat_upgrade.py apply --yes --lang hu|en [--agent NAME]
        [--adopt-onkep ROLE]... [--engine-src DIR] [--prove-question Q --prove-expect WORD...]

The downloaded files are checked against release.json before anything here runs. `plan` writes
nothing but .mentat/state/upgrade-plan.json; `apply` runs only that plan (an inventory that changed
since is a stop), only with --yes (the USER's yes), on a clean git tree, after a backup branch.
A fleet agent on a server (kind `box`) is never upgraded here: `fleet box-upgrade` does it.
Last line: `MENTAT-UPGRADE OK` or `MENTAT-UPGRADE HIBA: <the one thing>`.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted json.py here cannot shadow the stdlib
import mentat_verify  # noqa: E402  (first: nothing downloaded runs before it is checked)
_BAD = mentat_verify.verify(HERE)
if _BAD:
    print("MENTAT-UPGRADE HIBA: " + _BAD)
    sys.exit(1)
import mentat_upgrade_blocks as blocks  # noqa: E402
import mentat_upgrade_inv as inv_mod  # noqa: E402
import mentat_upgrade_onkep as onkep  # noqa: E402
import mentat_upgrade_steps as steps  # noqa: E402

BASE = "https://raw.githubusercontent.com/lipi4242/" + "mentat/v%s/"  # the tag of release.json
def release_version():
    for cand in (HERE / "release.json", HERE.parent.parent / "release.json"):  # installed, dev tree
        if cand.is_file():
            return json.loads(cand.read_text(encoding="utf-8"))["version"]
    raise SystemExit("MENTAT-UPGRADE HIBA: no release.json next to this tool")


def show_plan(root, inv, version, a):
    lines = ["KIND %s · from %s · to %s · language %s" % (inv["kind"], inv["installed"].get("brain") or
             (inv["engine"] or {}).get("version") or "?", version, a.lang)]
    lines += ["WARN " + w for w in inv["warnings"]]
    lines += ["PLAN %-9s %s" % s for s in steps.plan(inv, version, BASE % version, a.lang)]
    for role, action, _, d in onkep.plan(root, inv["brain_root"], a.lang):
        if action == "offer":
            lines += ["OFFER onkep %s (adopt only on the USER's yes: --adopt-onkep %s):" % (role, role), d]
    return lines


def apply(root, inv, version, a):
    base, lang = BASE % version, a.lang
    old = inv["installed"].get("brain") or ("pre-0.5" if inv["kind"] == "pre-0.5" else "old")
    name = steps.backup(root, old, version)
    if not name:
        return [], "the backup branch could not be made: nothing changed"
    done = ["BACKUP branch %s (the state before the upgrade; to undo the upgrade commit: git revert --no-edit "
            "<its sha>)" % name]
    text, changed, _ = blocks.refreshed((root / "AGENTS.md").read_text(encoding="utf-8"), lang, base)
    (root / "AGENTS.md").write_bytes(text.encode("utf-8"))
    done.append("AGENTS.md blocks refreshed: %s" % (", ".join(changed) or "none"))
    if inv["kind"] == "pre-0.5" and not (root / "mentat.json").exists():
        problem = steps.manifest(root, inv, version, lang, a.agent)
        if problem:
            return done, problem
    import mentat_scaffold as sc
    done += sc.scaffold(root, lang, base)
    import mentat_manifest as mm
    mm.update("brain", "installed", version, root)
    if inv["engine"]:
        problem = steps.engine(root, version, a.engine_src)
        if problem:
            return done, problem
        done.append("engine re-vendored at v%s, selftest green" % version)
    done += ["onkep %s: %s" % d for d in onkep.apply(root, inv["brain_root"], lang, version, a.adopt_onkep)]
    import mentat_self_image
    if mentat_self_image.write(root, lang):  # after the self-image blocks: it names the active roles
        done.append("AGENTS.md self-image rewritten")
    staged, problem = steps.commit(root, old, version, inv["brain_root"], lang)
    if problem:
        return done, problem
    done.append("committed %d file(s): %s" % (len(staged), inv_mod.git(root, "log", "--oneline", "-1").stdout.strip()))
    return done + check(root, lang, a), None


def check(root, lang, a):
    r = subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", lang, "--repo", str(root),
                        "--check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ["CHECK skeleton: " + (r.stdout.strip().splitlines() or ["?"])[-1]]
    import mentat_init_os
    tz = mentat_init_os.ensure_tzdata(lang)  # Windows only: an older install never got it
    out += [tz] if tz else []
    if a.prove_question and shutil.which("claude"):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        p = subprocess.run(["claude", "-p", a.prove_question], cwd=root, env=env, capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace")
        miss = [w for w in a.prove_expect if w.lower() not in p.stdout.lower()]
        out.append("CHECK fresh session: %s" % ("remembers %s" % ", ".join(a.prove_expect) if not miss and
                                                 p.returncode == 0 else "did NOT answer with %s" % ", ".join(miss)))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_upgrade.py")
    p.add_argument("command", choices=["inventory", "plan", "apply"])
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", choices=["hu", "en"])
    p.add_argument("--agent", help="pre-0.5 only: the agent's name (ask the USER)")
    p.add_argument("--yes", action="store_true", help="apply: the USER said yes to the plan")
    p.add_argument("--adopt-onkep", action="append", default=[], metavar="ROLE")
    p.add_argument("--engine-src", help="a local clone or mirror of the Mentat repo instead of GitHub")
    p.add_argument("--prove-question")
    p.add_argument("--prove-expect", action="append", default=[])
    a = p.parse_args(argv)
    root, version = pathlib.Path(a.repo).resolve(), release_version()
    inv = inv_mod.inventory(root)
    if a.command == "inventory":
        print(json.dumps(inv, indent=2, ensure_ascii=False))
        return 0
    a.lang = a.lang or inv["lang"]
    problem = inv_mod.blockers(inv, version, a.lang, a.agent, HERE)
    saved = root / ".mentat" / "state" / "upgrade-plan.json"
    if not problem and a.command == "plan":
        print("\n".join(show_plan(root, inv, version, a)))
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(json.dumps({"to": version, "fingerprint": inv_mod.fingerprint(inv)}).encode("utf-8"))
        print("MENTAT-UPGRADE OK: plan ready — show it to the USER; apply only after their yes")
        return 0
    if not problem and not a.yes:
        problem = "apply needs --yes: the USER's yes to the plan you showed"
    if not problem:
        try:
            ok = json.loads(saved.read_text(encoding="utf-8")) == {"to": version, "fingerprint": inv_mod.fingerprint(inv)}
        except (OSError, ValueError):
            ok = False
        problem = None if ok else "no current plan: run plan, show it to the USER, then apply"
    lines = []
    if not problem:
        lines, problem = apply(root, inv, version, a)
    print("\n".join(lines + ["MENTAT-UPGRADE HIBA: " + problem if problem else "MENTAT-UPGRADE OK"]))
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
