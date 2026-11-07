"""Pure mapping of one Linear export row to the backlog import payload. No I/O.

States (SPEC §6): Backlog/Todo/Triage -> draft; In Progress and In Review -> taken (needs a
mapped assignee, else draft); Done -> done; Canceled/Duplicate -> dropped. An unknown state
is an error, never a silent default.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

ARCHIVE_DAYS = 90
_STATES = {"backlog": "draft", "todo": "draft", "triage": "draft",
           "in progress": "taken", "in review": "taken", "done": "done",
           "canceled": "dropped", "cancelled": "dropped", "duplicate": "dropped"}
_HEAD = re.compile(r"^\W*(k[eé]sz,?\s*ha|done\s+when|acceptance(\s+criteria)?)\s*:?\W*$", re.I)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.+?)\s*$")
_PR = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/\d+")


class ImportError_(ValueError):
    pass


def parse_acs(description: str | None) -> list[str]:
    """Bullets under a 'Kész, ha:' / 'Done when:' / 'Acceptance' line."""
    acs: list[str] = []
    inside = False
    for line in (description or "").splitlines():
        if not inside:
            inside = bool(_HEAD.match(line))
            continue
        m = _BULLET.match(line)
        if m:
            acs.append(m.group(1))
        elif line.strip() or acs:
            break
    return acs


def map_stage(state: str | None, has_dev: bool) -> str:
    key = (state or "").strip().lower()
    if key not in _STATES:
        raise ImportError_(f"unknown Linear state {state!r}")
    stage = _STATES[key]
    return "draft" if stage == "taken" and not has_dev else stage


def _ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def is_archived(stage: str, row: dict, started_at: str) -> bool:
    """done/dropped and finished more than 90 days before the import started."""
    if stage not in ("done", "dropped"):
        return False
    end = _ts(row.get("completedAt") if stage == "done" else row.get("canceledAt"))
    return end is not None and end < _ts(started_at) - timedelta(days=ARCHIVE_DAYS)


def item_payload(row: dict, users: dict, started_at: str) -> dict:
    """Everything the server needs to create or complete this item in one transaction."""
    uuid = row["id"]
    dev = users.get(row.get("assignee") or "")
    stage = map_stage(row.get("state"), bool(dev))
    prefix, _, num = row["identifier"].rpartition("-")
    return {
        "ext_ref": f"linear:{uuid}", "project": prefix, "number": int(num),
        "title": row["title"], "description": row.get("description") or "",
        "priority": row.get("priority") or 0, "estimate": row.get("estimate"),
        "stage": stage, "dev": dev if stage == "taken" else None,
        "archived": is_archived(stage, row, started_at),
        "created_at": row.get("createdAt"), "labels": list(row.get("labels") or []),
        "acs": [{"source_id": f"linear:{uuid}:ac:{n}", "text": t}
                for n, t in enumerate(parse_acs(row.get("description")), 1)],
        "comments": [{"source_system": "linear", "source_id": c["id"], "body": c["body"],
                      "source_author": c.get("author"), "source_created_at": c["createdAt"]}
                     for c in row.get("comments") or []],
        "links": [{"url": a["url"], "title": a.get("title")}
                  for a in row.get("attachments") or [] if _PR.match(a.get("url") or "")],
        "idem_key": f"linear-import:{uuid}",
    }
