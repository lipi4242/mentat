"""A titok-kapu (titok_kapu.py) felhasználói szintű telepítése: a box MINDEN Claude-gyökerébe,
hogy minden ágens-session megkapja — a fogadó is, és az is, amelyikben nincs fleet-plugin.

    install(home) -> [jegyzet]   kód → ~/.mentat/bin/titok-kapu/<sha12>/ (0444/0555) + `current` symlink;
                                 PreToolUse-bejegyzés (onFailure: block) minden ~/.claude*/settings.json-ba
                                 (és a $CLAUDE_CONFIG_DIR-be); mentés: settings.json.bak-titok-<bélyeg>.
                                 Előtte az ágensek essentials-próbája és kanári (titok_kanari.py, 11-07):
                                 piros ágensnél nem ír semmit. CSAK a `fleet secrets hook install` hívja.
    selftest(home) -> [hiba]     a telepített hook futtatása: egy ártalmatlan Bash-hívás nem akadhat meg,
                                 egy kulcsfájl-olvasás nem mehet át (CISO Q5); az install hibával áll le
    problems(claude_home, home) -> [probléma]   a doctor-nak (hookguard.secrets_gate_problems)

A kód forrása a checkout `plugin/hooks/identitas/`-a: ez kerül a nyilvános kiadásba (a `security/`
nem, release_check.PRIVATE_DIRS). A plugin-másolat a plugin-sáv PR-jában jön (#109); amíg nincs bent,
a fejlesztői `security/eszkozok/identitas/` a forrás. Ha egyik sincs meg teljesen, az install HIBÁVAL
áll le (CISO Q6: a nyilvános kiadás eddig csendben kapu nélkül maradt volna). Ha mindkettő megvan,
bájtra egyeznek (tests/test_titok_telepit.py). A ~/.mentat/bin/ az identitás-kapu védett útja:
az ágens nem írhatja át. A saját bejegyzést cseréli (nem duplázza), a többi hook érintetlen.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fleet import PLUGIN_DIR, REPO_ROOT, titok_hely as H

RUNTIME = ("titok_kapu.py", "titok_minta.py", "titok_olvas.py", "titok_kod.py", "vedett.py", "vedett_ut.py",
           "agens_hatar.py", "agens_hatar_mod.py", "bash_szavak.py", "hatar_jel.py")
MARK = "titok-kapu"
MATCHER = "Bash|Read|Edit|MultiEdit|Write|NotebookEdit|Grep|Glob"
PLUGIN_SOURCE = PLUGIN_DIR / "hooks" / "identitas"
DEV_SOURCE = REPO_ROOT / "security" / "eszkozok" / "identitas"
SOURCES = (PLUGIN_SOURCE, DEV_SOURCE)


def missing(d: Path) -> list[str]:
    return [f for f in RUNTIME if not (d / f).is_file()]


def source() -> Path | None:
    return next((s for s in SOURCES if not missing(s)), None)


def code_dir(home: Path) -> Path:
    return home / ".mentat" / "bin" / MARK


def entry(home: Path, python: str | None = None, code: Path | None = None) -> dict:
    py = python or shutil.which("python3") or sys.executable
    cmd = f"{py} -I {(code or code_dir(home) / 'current') / 'titok_kapu.py'} --hook"
    return {"matcher": MATCHER, "hooks": [{"type": "command", "command": cmd, "timeout": 10, "onFailure": "block"}]}


def roots(home: Path) -> list[Path]:
    out = {home / ".claude"} | {p for p in home.glob(".claude*") if p.is_dir() and not p.is_symlink()}
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg and Path(cfg).resolve().is_relative_to(home.resolve()):  # a megadott HOME-on kívülre soha
        out.add(Path(cfg))
    return sorted(out)


def _ours(e) -> bool:
    return isinstance(e, dict) and any(MARK in str(h.get("command", "")) for h in e.get("hooks") or [])


def _code(src: Path, home: Path) -> str:
    """A kód a <sha12>/ alá; a `current` csak sikeres önteszt után vált rá (_switch)."""
    sha = hashlib.sha256(b"".join((src / f).read_bytes() for f in RUNTIME)).hexdigest()[:12]
    dest = code_dir(home) / sha
    if not all((dest / f).is_file() for f in RUNTIME):
        if dest.exists():
            os.chmod(dest, 0o755)
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for f in RUNTIME:
            shutil.copy2(src / f, dest / f)
            os.chmod(dest / f, 0o444)
        os.chmod(dest, 0o555)
    return sha


def _switch(home: Path, sha: str) -> None:
    cur, tmp = code_dir(home) / "current", code_dir(home) / "current.tmp"
    if not (cur.is_symlink() and os.readlink(cur) == sha):
        tmp.unlink(missing_ok=True)
        os.symlink(sha, tmp)
        os.replace(tmp, cur)


def _register(root: Path, home: Path, stamp: str) -> str | None:
    if not root.resolve().is_relative_to(home.resolve()):  # 2026-10-29: egy teszt a valódi gyökérbe írt
        return f"titok-kapu: {root} a HOME-on ({home}) kívül van — nem írom"
    p = root / "settings.json"
    try:
        data = json.loads(p.read_text() or "{}") if p.exists() else {}
    except ValueError:
        return f"{p}: nem JSON — nem nyúlok hozzá, a titok-kapu itt NINCS fent"
    hooks = data.setdefault("hooks", {})
    old = hooks.get("PreToolUse") or []
    new = [e for e in old if not _ours(e)] + [entry(home)]
    if new == old:
        return None
    if p.exists():
        shutil.copy2(p, p.with_name(f"settings.json.bak-titok-{stamp}"))
    hooks["PreToolUse"] = new
    mode = p.stat().st_mode & 0o777 if p.exists() else 0o600
    H.write_atomic(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n", mode)
    return f"titok-kapu: {p}"


#: (leírás, PreToolUse-bemenet, tiltani kell-e)
PROBES = (("ártalmatlan Bash (`true`)", {"tool_name": "Bash", "tool_input": {"command": "true"}}, False),
          ("kulcsfájl-olvasás (~/.ssh/id_ed25519)",
           {"tool_name": "Read", "tool_input": {"file_path": "~/.ssh/id_ed25519"}}, True),
          ("kézi systemd-unit (az ágens-határ él-e)",
           {"tool_name": "Write", "tool_input": {"file_path": "~/.config/systemd/user/onteszt.service"}}, True))


class SelfTestFailed(RuntimeError):
    """A telepített titok-kapu nem úgy dönt, ahogy kell: hangos hiba, nem csendes jegyzet."""


def selftest(home: Path, code: Path | None = None) -> list[str]:
    cmd = entry(home, code=code)["hooks"][0]["command"].split()
    env = {**os.environ, "HOME": str(home)}
    errs = []
    for label, data, want_deny in PROBES:
        try:
            r = subprocess.run(cmd, input=json.dumps({**data, "cwd": str(home)}), capture_output=True,
                               text=True, timeout=20, env=env)
        except (OSError, subprocess.TimeoutExpired) as e:
            errs.append(f"{label}: a hook nem fut ({type(e).__name__})")
            continue
        denied = '"deny"' in r.stdout
        if r.returncode != 0 or denied != want_deny:
            errs.append(f"{label}: {'átengedte' if want_deny else 'megtagadta'} (kód {r.returncode})")
    return errs


def install(home: Path | None = None, agents: list[dict] | None = None, force: bool = False,
            dry_run: bool = False) -> list[str]:
    """`agents`: a próbált ágensek (None = a registry ezen a boxon); `force`: piros essentials mellett is."""
    from fleet import essentials, titok_kanari as K
    home = Path(home or Path.home())
    src = source()
    if src is None:
        raise SelfTestFailed("titok-kapu: NINCS telepítve — a checkoutban nincs a hook teljes kódja "
                             f"(plugin/hooks/identitas): hiányzik {', '.join(missing(PLUGIN_SOURCE))}")
    sha, stamp = _code(src, home), time.strftime("%Y%m%d-%H%M%S")
    errs = selftest(home, code_dir(home) / sha)
    if errs:  # a hibás kód nem lesz `current`, és a beállításokba sem kerül: minden ágenst kizárna
        raise SelfTestFailed("titok-kapu önteszt HIBÁS, nem telepítem: " + "; ".join(errs))
    try:  # 11-07: essentials-próba a jelölt kódon, kanári-gyökér, csak utána a többi
        notes = K.rollout(home, sha, stamp, essentials.local_agents() if agents is None else agents, force, dry_run)
    except K.Refused as e:
        raise SelfTestFailed(str(e)) from None
    return notes + [f"titok-kapu kód: {code_dir(home) / sha} ({len(roots(home))} Claude-gyökér, önteszt rendben)"]


def in_use(home: Path) -> bool:
    """Él-e már a boxon a titok-kapu (kód vagy leltár)."""
    return (code_dir(home) / "current").exists() or H.inventory_path(home).exists()


def problems(claude_home: Path, home: Path | None = None, required: bool = False) -> list[str]:
    """Ha a boxon már él a titok-kapu (kód vagy leltár), minden Claude-gyökérben fent kell lennie.
    `required=True` (a `hook status`): akkor is hiba, ha a boxon sosem települt."""
    home = Path(home or Path.home())
    if not required and not in_use(home):
        return []
    label = "~/" + Path(claude_home).name + "/settings.json"
    try:
        pre = json.loads((Path(claude_home) / "settings.json").read_text()).get("hooks", {}).get("PreToolUse") or []
    except (OSError, ValueError, AttributeError):
        pre = []
    own = [h for e in pre if _ours(e) for h in e["hooks"]]
    if not own or own[0].get("onFailure") != "block":
        return [f"titok-kapu hiányzik ({label}): `fleet secrets hook install`"]
    if not (code_dir(home) / "current" / "titok_kapu.py").is_file():
        return [f"titok-kapu kódja hiányzik ({code_dir(home)}/current): `fleet secrets hook install`"]
    return []
