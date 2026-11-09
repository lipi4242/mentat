"""11-07: képesség-próba — az ágens alapfunkciói ténylegesen LEFUTNAK-e, nem csak engedélyezettek.

    check(entry, home, run=subprocess.run) -> {"red": [...], "unknown": [...], "ok": [...]}

Az essentials-próba (essentials.py, #51) azt nézi, hogy a titok-kapu ENGEDNÉ-e a küldést, a todót,
a gitet. Ez a réteg le is futtatja őket, korlátosan (lépésenként TIMEOUT_S, nincs Telegram-hívás):

  küldés    `send.mjs --dry-run --chat $TELEGRAM_GROUP_CHAT_ID`, a unit env-fájljaival (token +
            chat + kapcsolók + kapu + napló; bridge/lib/dry-run.mjs)
  todo      `mentat-todo me` (egy kérés), ha a boxon van todo-beállítás (~/.config/todo/env)
  állapot   a motor saját állapotfájljai olvashatók és érvényes JSON-ok
  git       `git status` az ágens repójában, és a .git írható
  todo-ébresztés  a híd todo-pollja friss-e, van-e feldolgozatlan ébresztés (kepesseg_todo.py)

A futtatás tiszta környezetben megy (HOME, PATH, FLEET_AGENT + a unit env-fájljai), nem a hívó
shelljéből: egy operátori shellben exportált token különben hamis zöldet adna. Az env-fájlok
értékei a gyerekfolyamatban maradnak; a kimenetbe csak a saját, ismert hibasoraink kerülnek.
A unit nélküli ágenst nem méri: azt a processz-jel és az essentials token-sora már mutatja.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from fleet import REPO_ROOT, essentials_env as E, kepesseg_todo

TIMEOUT_S = 20
STATE_FILES = ("data/state/anytime-state.json", "scripts/anytime/anytime-state-v2.json",
               "scripts/review-state/current.json", "data/state/todo-cursor.json")
# A shell `.`-ja egy hibás env-fájlnál a sor egy darabját is kiírhatja: csak ismert sorainkat mutatjuk.
SAFE_LINE = re.compile(r"^(dry-run HIBA: |missing TELEGRAM_BOT_TOKEN|nincs TELEGRAM_GROUP_CHAT_ID|mentat-todo: |"
                       r"ismeretlen kapcsolo)")
# A unit env-fájljai (pozicionálisan, `--`-ig), utána a futtatandó parancs. A küldésnél a chat a
# betöltött env-ből jön, ezért ott a parancs maga a send.mjs útja ($1).
LOAD = ('set -a; while [ $# -gt 0 ] && [ "$1" != -- ]; do if [ -r "$1" ]; then . "$1"; fi; shift; done; '
        'shift; set +a; export FLEET_AGENT="$KEPESSEG_AGENT"; ')
SEND = LOAD + ('[ -n "${TELEGRAM_GROUP_CHAT_ID:-}" ] || { echo "nincs TELEGRAM_GROUP_CHAT_ID a unit env-jében" >&2; '
               'exit 65; }; exec node "$1" --dry-run --chat "$TELEGRAM_GROUP_CHAT_ID" -- kepesseg-proba')
RUN = LOAD + 'exec "$@" 2>&1'


def _base_env(entry: dict, home: Path) -> dict:
    path = f"{home}/.bun/bin:{home}/.local/bin:/usr/local/bin:/usr/bin:/bin:{os.environ.get('PATH', '')}"
    return {"HOME": str(home), "PATH": path, "LANG": "C.UTF-8", "KEPESSEG_AGENT": entry["agent"]}


def _safe(out: str, code: int) -> str:
    lines = [ln.strip() for ln in (out or "").splitlines() if SAFE_LINE.match(ln.strip())]
    return lines[-1][:200] if lines else f"kód {code} (a részletek nem kerülnek ki: lehet env-fájl-hiba)"


def _wrapped(entry, home, files, script, argv, run, cwd):
    cmd = ["sh", "-c", script, "kepesseg", *[str(f) for f in files], "--", *argv]
    try:
        r = run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, env=_base_env(entry, home), cwd=str(cwd))
    except subprocess.TimeoutExpired:
        return None, f"nem válaszolt {TIMEOUT_S} s alatt"
    except OSError as e:
        return None, f"nem indítható ({type(e).__name__})"
    return r, None


def _send(entry, home, files, run, cwd, out):
    send = home / ".config" / entry["agent"] / "sub-etha" / "send.mjs"
    if not send.is_file():
        out["red"].append(f"küldés: nincs telepítve a send.mjs ({entry['agent']}) — `fleet bridge install {entry['agent']}`")
        return
    r, err = _wrapped(entry, home, files, SEND, [str(send)], run, cwd)
    if err:
        out["red"].append(f"küldés: a send.mjs {err}")
    elif r.returncode == 0:
        out["ok"].append("küldés (dry-run)")
    elif r.returncode == 64 and "--dry-run" in (r.stderr or ""):
        out["unknown"].append(f"küldés: a telepített send.mjs nem ismeri a --dry-run-t — `fleet bridge install {entry['agent']}`")
    else:
        out["red"].append(f"küldés a tulajdonosnak NEM MENNE: {_safe((r.stderr or '') + (r.stdout or ''), r.returncode)}")


def _todo(entry, home, files, run, cwd, out):
    if not (home / ".config" / "todo" / "env").is_file():
        return  # a boxon nincs todo: nincs mit mérni
    exe = shutil.which("mentat-todo", path=_base_env(entry, home)["PATH"]) or str(REPO_ROOT / "bin" / "mentat-todo")
    r, err = _wrapped(entry, home, files, RUN, [exe, "me"], run, cwd)
    if err:
        out["red"].append(f"todo: `mentat-todo me` {err}")
    elif r.returncode == 0:
        out["ok"].append("todo (mentat-todo me)")
    else:
        out["red"].append(f"todo: `mentat-todo me` hibás: {_safe(r.stdout, r.returncode)}")


def _state(wd: Path, out: dict) -> None:
    for rel in STATE_FILES:
        p = wd / rel
        if not p.is_file():
            continue
        try:
            json.loads(p.read_text())
            out["ok"].append(f"állapot: {rel}")
        except (OSError, ValueError) as e:
            out["red"].append(f"saját állapot nem olvasható: {rel} ({type(e).__name__})")


def _git(wd: Path, run, out: dict) -> None:
    try:
        r = run(["git", "-C", str(wd), "status", "--porcelain"], capture_output=True, text=True, timeout=TIMEOUT_S)
        top = run(["git", "-C", str(wd), "rev-parse", "--absolute-git-dir"], capture_output=True, text=True,
                  timeout=TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        out["red"].append(f"git: nem fut a repóban ({type(e).__name__})")
        return
    if r.returncode != 0 or top.returncode != 0:
        out["red"].append(f"git: `git status` hibás a repóban ({wd}), kód {r.returncode}")
    elif not os.access(top.stdout.strip(), os.W_OK):
        out["red"].append(f"git: a {top.stdout.strip()} nem írható — commit nem menne")
    else:
        out["ok"].append("git")


def is_desktop(entry: dict) -> bool:
    """Saját gépen futó tag (Claude Desktop/Code, nincs always-on processz, unit és híd)."""
    return entry.get("supervision") == "none" and entry.get("status") != "dormant"


def check(entry: dict, home: Path, run=subprocess.run, desktop: bool = False) -> dict:
    """`desktop=True` (paritás): a felügyelet nélküli tagot is méri — a saját sessionje
    kéri (`fleet flotta report`). Unit és híd nélkül: todo, saját állapot, git."""
    out = {"red": [], "unknown": [], "ok": []}
    if entry.get("status") == "dormant" or (entry.get("supervision") == "none" and not desktop):
        return out
    files = [] if is_desktop(entry) else E.unit_env_files(entry, home)
    if files is None:  # a unit hiányát a processz-jel és (hidas ágensnél) a token-előfeltétel már méri
        return out
    wd = E.workdir(entry, home)
    if not wd.is_dir():
        out["red"].append(f"képesség: nincs meg az ágens repója ({wd})")
        return out
    if E.bridged(entry):
        _send(entry, home, files, run, wd, out)
    _todo(entry, home, files, run, wd, out)
    kepesseg_todo.check(entry, home, out)  # 11-08: a híd todo-ébresztése
    _state(wd, out)
    _git(wd, run, out)
    if entry.get("tick_gate"):   # tick-kapu: a kapu nyoma — tétlen = zöld, elakadt timer/szkript = piros
        from fleet.tick_gate_health import kepesseg_line
        line = kepesseg_line(entry, home)
        if line:
            out[line[0]].append(line[1])
    return out


def summary(res: dict) -> str:
    return "képesség: " + (" · ".join(res["ok"]) + " ✓" if res["ok"] else "nincs zöld lépés")
