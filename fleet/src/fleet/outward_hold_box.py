"""A kifelé-tartás jelzője EGY ágens repójában, a saját boxán — önálló, csak stdlib.

Mint az agent_probe.py: a hívó helyben importálja, vagy ssh-n a box `python3 -`-jának
stdin-jére küldi, ezért nem importál a `fleet` csomagból (a box fleet-kódja régi lehet).

    python3 outward_hold_box.py '{"op": "set|release|show", "workdir": "%h/x", "marker": {...}}'

A jelzőt az anytime motor olvassa (anytime_engine/hold.py): amíg él, minden tick dry-run,
és semmi nem megy ki. Út és szabályok ugyanazok, mint ott:
  <workdir>/data/state/kifele-tartas.json  {"until": ISO, "reason", "set_by", "set_at"}
  lejárt `until` → hatástalan; legfeljebb 24 óra az írástól (mtime); olvashatatlan → tart.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_HOURS = 24
REL = Path("data") / "state" / "kifele-tartas.json"


def repo(workdir, home=None):
    return Path(str(workdir).replace("%h", str(home or Path.home())))


def _aware(text):
    t = datetime.fromisoformat(str(text))
    return t if t.tzinfo else t.astimezone()   # naive = a box helyi ideje


def read(wd, now=None):
    """{present, active, until, reason, set_by, broken, expired, path} — csak olvas."""
    p = wd / REL
    out = {"path": str(p), "present": False, "active": False}
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return out
    now = now or datetime.now(timezone.utc)
    cap = datetime.fromtimestamp(mtime, tz=timezone.utc) + timedelta(hours=MAX_HOURS)
    out["present"] = True
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        until = min(_aware(data["until"]), cap)
        out.update(reason=data.get("reason") or "", set_by=data.get("set_by") or "", broken=False)
    except (OSError, ValueError, TypeError, KeyError):
        until = cap
        out.update(reason="olvashatatlan jelző — a motor biztonságból tart", set_by="", broken=True)
    out["until"] = until.astimezone().isoformat(timespec="seconds")
    out["active"] = until > now
    out["expired"] = not out["active"]
    return out


def engine_knows(wd):
    """Ismeri-e a motor a jelzőt? Ha nem, a jelző hatástalan — ezt hangosan kell mondani."""
    try:
        r = subprocess.run([sys.executable, "-c", "import anytime_engine.hold"], cwd=str(wd),
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run(spec, home=None):
    wd = repo(spec["workdir"], home)
    if not wd.is_dir():
        return {"ok": False, "error": "nincs ilyen ágens-repó a boxon: %s" % wd}
    p = wd / REL
    op = spec["op"]
    if op == "set":
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(".%s.%d.tmp" % (p.name, os.getpid()))
        tmp.write_text(json.dumps(spec["marker"], ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        return {"ok": True, "hold": read(wd), "engine_knows": engine_knows(wd)}
    if op == "release":
        existed = p.exists()
        p.unlink(missing_ok=True)
        return {"ok": not p.exists(), "removed": existed, "path": str(p)}
    return {"ok": True, "hold": read(wd)}


if __name__ == "__main__":
    print(json.dumps(run(json.loads(sys.argv[1])), ensure_ascii=False))
