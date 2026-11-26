"""Whose text an agent may act on: the trusted list, and the notice that replaces a stranger's text.

With a list configured, a row whose creator (created_by) is not on it reaches the agent only as a
notice: the keys the caller names (ids, dates, who), never its title, description or other free text. Dropping the text in code is the guard: what the
agent never reads it cannot follow, whatever the prompt says. No list = nobody is a stranger
(every row is still framed as data, see untrusted.py). Not updated_by: the server sets it on every
write, a comment or a stage move included, so it names the last actor, not the text's author. Where a
source does name the text's author (`text_updated_by`, the admin's case reads), a stranger there counts too.
"""
from __future__ import annotations

import os
from typing import Any, Iterable

from . import config
from . import mentat_manifest as mm


def trusted_list(handle: str | None = None, root=None) -> set[str] | None:
    """ANYTIME_TODO_TRUSTED (comma list) or mentat.json components.engine.todo_trusted, plus the agent
    itself (`handle`). None = no list configured. A handle `x` also matches the principal id `p_x`."""
    raw = os.environ.get("ANYTIME_TODO_TRUSTED")
    if raw is not None:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        try:
            doc = mm.load(root or config.repo_root().resolve()) or {}
        except mm.ManifestError:
            return None
        listed = ((doc.get("components") or {}).get("engine") or {}).get("todo_trusted")
        if not isinstance(listed, list):
            return None
        names = [str(x) for x in listed]
    return {v for n in names + ([handle] if handle else []) for v in (n, f"p_{n}")}


def from_stranger(row: dict[str, Any], trusted: set[str] | None, *, unattributed_ok: bool = False) -> bool:
    """Did someone off the list create this row, or last write its text? A row with no creator counts
    as a stranger's, unless the source records no creators at all (`unattributed_ok`: the agent's own
    store). A null `text_updated_by` is a person's edit (or none recorded), not a stranger's."""
    if trusted is None:
        return False
    if row.get("created_by") is None and not unattributed_ok:
        return True
    return any(row.get(k) is not None and row[k] not in trusted for k in ("created_by", "text_updated_by"))


def notice(row: dict[str, Any], keep: Iterable[str]) -> dict[str, Any]:
    """Only the named keys (never free text) and `withheld: True`."""
    return {**{k: row[k] for k in keep if k in row}, "withheld": True}


def screen(rows: Iterable[dict[str, Any]], trusted: set[str] | None, keep: Iterable[str],
           *, unattributed_ok: bool = False) -> list[dict[str, Any]]:
    """Each row as it is, or as a notice when a stranger wrote it."""
    keep = tuple(keep)
    return [notice(r, keep) if from_stranger(r, trusted, unattributed_ok=unattributed_ok) else r
            for r in rows]
