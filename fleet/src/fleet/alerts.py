"""Riasztás emberhez a boxról.

Az utak (11-07 óta nincs külön riasztó bot):
  1. a képesség-hiba (az ágens fut, de nem tud küldeni/todózni/gitezni) a központi
     flotta-ellenőrzésbe megy (flotta_report.py → a Mentat Admin `flotta` pluginja); ott a
     felelős ágens kap feladatot, és ha nem oldja meg, e-mail megy a tulajdonosnak. Ez a modul
     ilyenkor csak a tartalékot adja (`independent_only=True`: a beteg ágens hídján SOHA);
  2. a többi riasztás (karantén, dup, rc) az ágens saját hídján megy, ha van;
  3. ha egyik sem ment ki: fájl (`~/.config/fleet/state/alerts-undelivered.jsonl`) + stderr;
     a `fleet doctor` box-sora ezt pirosan mutatja, amíg ott van (doctor_box.py).

Egy riasztás egyszer megy ki egy adott kulcsra (`~/.config/fleet/state/
alerts.json`), különben 5 percenként ugyanaz ismétlődne.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fleet import CONFIG_DIR, BRIDGE_DIR

ALERTS_PATH = CONFIG_DIR / "state" / "alerts.json"
UNDELIVERED = CONFIG_DIR / "state" / "alerts-undelivered.jsonl"


def _load() -> dict:
    try:
        return json.loads(ALERTS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _env_from_file(path: Path) -> dict:
    env = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def send_telegram(text: str, *, env_file: Path | list[Path], send_mjs: Path = BRIDGE_DIR / "send.mjs") -> bool:
    files = env_file if isinstance(env_file, list) else [env_file]  # 11-07: a unit összes env-fájlja
    env = {k: v for k, v in os.environ.items() if k != "TELEGRAM_BOT_TOKEN"}  # csak a fájlból jöhet
    for f in files:
        env.update(_env_from_file(f))
    chat = env.get("TELEGRAM_GROUP_CHAT_ID") or env.get("TELEGRAM_ALERT_CHAT_ID")
    if not env.get("TELEGRAM_BOT_TOKEN") or not chat:
        return False
    env.setdefault("BRIDGE_STATE_DIR", str(CONFIG_DIR))
    try:
        r = subprocess.run(["node", str(send_mjs), "--chat", chat, "--", text],
                           env=env, capture_output=True, text=True, timeout=30)
        return r.returncode in (0, 3)
    except (OSError, subprocess.TimeoutExpired):
        return False


def _drop(key: str, text: str) -> None:
    try:
        UNDELIVERED.parent.mkdir(parents=True, exist_ok=True)
        with UNDELIVERED.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "key": key, "text": text}, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a stderr-sor marad; a riasztás nem omlaszthatja össze a hívót


def alert(key: str, text: str, *, agent_env_file: Path | list[Path] | None = None,
          independent_only: bool = False) -> str:
    """Kiküldi egyszer; visszaadja: 'sent-agent' | 'dup' | 'stderr' (fájlba is).
    `independent_only`: a képesség-hiba tartaléka — Telegramra nem megy, csak fájlba."""
    seen = _load()
    if seen.get(key):
        return "dup"
    res = "stderr"
    if agent_env_file and not independent_only and send_telegram(text, env_file=agent_env_file):
        res = "sent-agent"
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen[key] = True
    ALERTS_PATH.write_text(json.dumps(seen, indent=2))
    if res == "stderr":
        _drop(key, text)
        print(f"[fleet alert] {text}", file=sys.stderr)
    return res


def clear(key_prefix: str) -> None:
    seen = _load()
    changed = {k: v for k, v in seen.items() if not k.startswith(key_prefix)}
    if changed != seen:
        ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_PATH.write_text(json.dumps(changed, indent=2))
