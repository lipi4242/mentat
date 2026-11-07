"""localday - "today" in the agent's own timezone, never the box's UTC.

The zone is, first wins: ANYTIME_TZ, mentat.json components.engine.timezone
(what `anytime_engine.setup --tz` records), else the machine's local time.
A zone that does not exist is a refusal: a guessed day is worse than a stop.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from common import CasesError


def zone_name(root):
    if os.environ.get("ANYTIME_TZ"):
        return os.environ["ANYTIME_TZ"]
    try:
        doc = json.loads((Path(root) / "mentat.json").read_text(encoding="utf-8"))
        return ((doc.get("components") or {}).get("engine") or {}).get("timezone") or None
    except (OSError, ValueError, AttributeError):
        return None


def today(root, now=None):
    """YYYY-MM-DD in the agent's zone. `now` (aware, tests) defaults to the clock."""
    now = now or datetime.now(timezone.utc)
    name = zone_name(root)
    if not name:
        return now.astimezone().date().isoformat()
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        return now.astimezone(ZoneInfo(name)).date().isoformat()
    except (ZoneInfoNotFoundError, ValueError):
        raise CasesError("unknown timezone %r (an IANA name like Europe/Budapest; fix "
                         "components.engine.timezone in mentat.json)" % name)
