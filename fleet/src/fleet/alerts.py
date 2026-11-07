"""Riasztás emberhez. A riasztó út független a beteg ágens hídjától, ha van
`FLEET_ALERT_ENV` (egy telegram.env a flotta saját botjával); különben az
ágens saját hídjával megy — ami pont akkor bukhat, amikor kell, ezért a
`doctor` ezt is kiírja.

Egy riasztás egyszer megy ki egy adott kulcsra (`~/.config/fleet/state/
alerts.json`), különben 5 percenként ugyanaz ismétlődne.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

from fleet import CONFIG_DIR, BRIDGE_DIR

ALERTS_PATH = CONFIG_DIR / "state" / "alerts.json"


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


def send_telegram(text: str, *, env_file: Path, send_mjs: Path = BRIDGE_DIR / "send.mjs") -> bool:
    env = {**os.environ, **_env_from_file(env_file)}
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


def alert(key: str, text: str, *, agent_env_file: Path | None = None) -> str:
    """Kiküldi egyszer; visszaadja: 'sent' | 'dup' | 'stderr'."""
    seen = _load()
    if seen.get(key):
        return "dup"
    env_file = os.environ.get("FLEET_ALERT_ENV")
    path = Path(env_file) if env_file else agent_env_file
    sent = bool(path) and send_telegram(text, env_file=path)
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen[key] = True
    ALERTS_PATH.write_text(json.dumps(seen, indent=2))
    if not sent:
        print(f"[fleet alert] {text}", file=sys.stderr)
        return "stderr"
    return "sent"


def clear(key_prefix: str) -> None:
    seen = _load()
    changed = {k: v for k, v in seen.items() if not k.startswith(key_prefix)}
    if changed != seen:
        ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_PATH.write_text(json.dumps(changed, indent=2))
