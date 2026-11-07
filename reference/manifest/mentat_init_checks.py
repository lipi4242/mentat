"""Preflight and selftest for mentat_init.py: machine checks, no LLM.

preflight(engine, offline) -> (lines, problem or None)
selftest(root, lang, engine, prove) -> (lines, problem or None)
git_identity(root, name, email) -> ((name, email), problem or None)
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

import mentat_init_os as osx

HERE = pathlib.Path(__file__).resolve().parent
MIN_CLAUDE = (2, 1, 295)  # PreToolUse onFailure "block": older Claude Code fails a hook OPEN
MIN_FREE = 200 * 1024 * 1024


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 30), **kw)
    except (OSError, subprocess.TimeoutExpired):
        return None


def preflight(engine, offline):
    lines, ok = [], []
    if not shutil.which("git"):
        return lines, "nincs git: `%s`" % osx.hint("git")
    ok.append("git")
    if sys.version_info < (3, 9):
        return lines, "a python3 túl régi (%d.%d), 3.9+ kell" % sys.version_info[:2]
    ok.append("python %d.%d" % sys.version_info[:2])
    shell = osx.hook_shell()
    if not shell:  # Windows: hooks would fall back to PowerShell, the POSIX guard hook fails closed
        return lines, "nincs Git Bash (Windowson a Claude Code ebben futtatja a hookokat): `%s`" % osx.hint("git")
    r = _run(shell + ["python3 -c 'import sys; print(sys.version_info >= (3, 9))'"])
    if not r or r.stdout.strip() != "True":  # the hook calls `python3`, not this interpreter
        return lines, "a hookok nem találnak python3-at (3.9+): `%s`" % osx.hint("python3")
    r = _run(["claude", "--version"]) if shutil.which("claude") else None
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", r.stdout.strip()) if r and r.returncode == 0 else None
    if m and tuple(map(int, m.groups())) < MIN_CLAUDE:
        return lines, ("a Claude Code %s régi: a szerep-őr hibája ezen átengedne, %s+ kell "
                       "(`claude update`)" % (m.group(0), ".".join(map(str, MIN_CLAUDE))))
    ok.append("claude %s" % m.group(0) if m else "claude: nem található (a verzió nem ellenőrizhető)")
    if shutil.disk_usage(".").free < MIN_FREE:
        return lines, "kevés a szabad hely (200 MB kell)"
    if engine and not offline:
        try:
            urllib.request.urlopen("https://raw.githubusercontent.com/", timeout=5)
            ok.append("hálózat")
        except Exception:  # noqa: BLE001 - any failure: offline
            return lines, "nincs hálózat a GitHub felé: --engine-src <helyi Mentat-klón> vagy később"
    lines.append("Előfeltételek: " + ", ".join(ok) + ".")
    return lines, None


def git_identity(root, name, email):
    """Use what git already has; set only what is missing, for this repo only. An e-mail is
    never made up: with none set and none given, the USER is asked (the commit needs one)."""
    have = [(_run(["git", "-C", str(root), "config", k]) or subprocess.CompletedProcess([], 1, "")).stdout.strip()
            for k in ("user.name", "user.email")]
    if email and ("@" not in email or email.rsplit("@", 1)[1].lower() in ("localhost", "localdomain", "local")):
        return have, "a --git-email nem valódi cím (%s): a FELHASZNÁLÓ saját e-mail-címe kell" % email
    if not have[1] and not email:
        return have, ("nincs git-identitás a mentéshez: kérdezd meg a FELHASZNÁLÓT, milyen névvel és "
                      "e-mail-címmel jelenjenek meg a mentései, aztán ugyanez újra --git-name \"…\" "
                      "--git-email \"…\" kiegészítéssel (kitalált címet ne adj meg)")
    return [have[0] or name, have[1] or email], None


def _guard_probe(root):
    """The installed hook, as Claude Code runs it: an outside read must not pass silently."""
    s = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = [h for e in s["hooks"]["PreToolUse"] for h in e["hooks"] if "szerep_guard" in h["command"]]
    if not pre or pre[-1].get("onFailure") != "block":
        return "a szerep-őr hookja nincs bekötve (onFailure: block)"
    if not (root / ".mentat/bin/bekotes/szerep_guard.py").is_file():
        return None  # dev tree / not vendored yet: the hook blocks until step 1 fetches it
    outside = _decide(root, pre[-1]["command"], os.path.expanduser("~/.claude/projects/other/memory/notes.md"))
    if outside not in ("ask", "deny"):
        return "a szerep-őr nem állította meg a kívüli olvasást"
    if _decide(root, pre[-1]["command"], str(root / "AGENTS.md")) != "allow":  # a deny-all guard is not green
        return "a szerep-őr a munkamappán belüli olvasást is megállítja"
    return None


def _decide(root, command, path):
    """The hook's decision on a Read of `path`: allow (no output, exit 0), ask, deny or None."""
    payload = {"session_id": "init", "cwd": str(root), "permission_mode": "default", "tool_name": "Read",
               "tool_input": {"file_path": path}}
    r = _run((osx.hook_shell() or ["/bin/sh", "-c"]) + [command], input=json.dumps(payload), env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)),
             cwd=root)
    if r is None or r.returncode != 0:
        return None
    if not r.stdout.strip():
        return "allow"
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        return None


def selftest(root, lang, engine, prove, agent, user):
    py = sys.executable
    r = _run([py, str(HERE / "mentat_scaffold.py"), "--lang", lang, "--repo", str(root), "--check"])
    open_ph = [ln for ln in (r.stdout.splitlines() if r else ["?"]) if "OPEN placeholder" not in ln
               and not ln.startswith(("OK", "  "))]
    if r is None or (r.returncode != 0 and [x for x in open_ph if x.strip()]):
        return [], "a váz ellenőrzése nem zöld: " + (r.stdout.strip().splitlines() or ["?"])[0] if r else "?"
    problem = _guard_probe(root)
    if problem:
        return [], problem
    r = _run([py, str(HERE / "mentat_brain.py"), "due"], cwd=root)
    if r is None or r.returncode != 0:
        return [], "a jegyzet-parancs nem fut: " + ((r.stderr if r else "") or "?").strip()[:120]
    lines = []
    if engine:
        r = _run([py, "-m", "anytime_engine.selftest", "-q"], cwd=root, timeout=300)
        if r is None or r.returncode != 0:
            return [], "a motor selftestje nem zöld: " + ((r.stdout + r.stderr) if r else "?").strip()[-160:]
    if prove and shutil.which("claude"):
        q = "Hogy hívnak engem, és téged? Csak a betöltött utasításaidból válaszolj, ne használj eszközt."
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        r = _run(["claude", "-p", q], cwd=root, env=env, timeout=120)
        seen = r is not None and r.returncode == 0 and agent in r.stdout and user.split()[0] in r.stdout
        lines.append("Friss session: %s." % ("magától tudja mindkét nevet" if seen else "nem sikerült ellenőrizni"))
    return lines, None
