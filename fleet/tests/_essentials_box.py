"""Közös fixtúra a 11-07 essentials-tesztekhez: egy kitalált box két hidas ágenssel.
`vilma` unitja a telegram.env-et tölti (zöld); `szervezo` unitja csak az agent.env-et (a 11-07-i
paul-cfo alakja: nincs token a unit env-jében). Hamis értékek, ideiglenes HOME."""
from __future__ import annotations
import json
import shutil
import tempfile
from pathlib import Path

FAKE = "HAMIS-ERTEK-NEM-VALODI-0123456789"


def entry(agent: str, **kw) -> dict:
    from fleet import registry
    base = {"agent": agent, "workdir": f"%h/{agent}", "host": "box",
            "bridge": {"unit": f"{agent}-telegram-bridge.service"}}
    return registry.normalize({**base, **kw})


def make_box(case) -> Path:
    home = Path(tempfile.mkdtemp()).resolve()
    case.addCleanup(shutil.rmtree, home, True)
    udir = home / ".config/systemd/user"
    udir.mkdir(parents=True)
    for a, env in (("vilma", "telegram.env"), ("szervezo", "agent.env")):
        (home / a / "bin").mkdir(parents=True)
        (home / ".config" / a / "jobs").mkdir(parents=True)
        (home / ".config" / a / "telegram.env").write_text(f"TELEGRAM_BOT_TOKEN={FAKE}\nTELEGRAM_GROUP_CHAT_ID=-1\n")
        (home / ".config" / a / "agent.env").write_text(f"OPENAI_API_KEY={FAKE}\n")
        (udir / f"{a}.service").write_text(f"[Service]\nEnvironmentFile=-%h/.config/{a}/{env}\n")
    (home / ".config/vilma/jobs/todo_poll.py").write_text("print(1)\n")
    (home / ".claude").mkdir()
    (home / ".claude/settings.json").write_text(json.dumps({"model": "x"}))
    (home / ".claude-vilma").mkdir()
    (home / ".claude-vilma/settings.json").write_text(json.dumps({"hooks": {}}))
    return home


def leltar(home: Path, *paths: Path) -> None:
    """Egy (régi, hibás) leltár kézzel: a 11-07-i box a 0700-as todo_poll.py-t is listázta."""
    d = home / ".mentat/titkok"
    d.mkdir(parents=True, exist_ok=True)
    files = [{"path": str(p), "class": "env", "agent": "vilma", "dev": p.stat().st_dev, "ino": p.stat().st_ino}
             for p in paths]
    (d / "leltar.json").write_text(json.dumps({"schema": 1, "files": files}))


def ours(home: Path, root: str) -> list:
    pre = json.loads((home / root / "settings.json").read_text()).get("hooks", {}).get("PreToolUse") or []
    return [h for e in pre for h in e.get("hooks", []) if "titok-kapu" in h.get("command", "")]
