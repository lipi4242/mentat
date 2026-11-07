"""Shared plumbing of the work-store commands (cli_task, cli_case, cli_item).

- The actor is always the token's principal: no command takes an "as" field.
- Every mutation sends `expected_rev`. Without --rev the current rev is read
  first; the server still refuses a write that races another one (409).
- Every create sends an `idem_key`. Without --idem it is derived from the
  request itself, so running the same command twice (a lost answer, a crash)
  creates one row, not two. Pass --idem to create a deliberate twin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from anytime_engine import config

from . import settings
from .api import Client, TodoApiError, seg


class UsageError(Exception):
    """The command line is wrong; nothing was sent."""


def client() -> tuple[Client, settings.Settings]:
    s = settings.load(config.repo_root().resolve())
    if s is None:
        raise settings.TodoConfigError("the todo pack is not configured (TODO_API + TODO_HANDLE)")
    return Client(s.api, s.token()), s


def idem(explicit: str | None, kind: str, body: dict[str, Any]) -> str:
    if explicit:
        return explicit
    blob = json.dumps({"kind": kind, **body}, sort_keys=True, ensure_ascii=False)
    return "cli:" + hashlib.sha256(blob.encode()).hexdigest()[:32]


def rev_of(c: Client, path: str, rev: int | None) -> int:
    if rev is not None:
        return rev
    row = c.get_json(path)
    if not isinstance(row, dict) or not isinstance(row.get("rev"), int):
        raise TodoApiError(f"todo API answered {path} without a rev")
    return row["rev"]


def task_path(task_id: str) -> str:
    return "/tasks/" + seg(task_id)


def show(out: Any) -> int:
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def text(value: str | None, name: str) -> str | None:
    """A free-text option: None stays None, blank is refused."""
    if value is None:
        return None
    if not value.strip():
        raise UsageError(f"--{name} must not be blank")
    return value.strip()


def required(value: str | None, name: str) -> str:
    out = text(value, name)
    if out is None:
        raise UsageError(f"--{name} is required")
    return out


def add_rev(p: argparse.ArgumentParser) -> None:
    p.add_argument("--rev", type=int, help="the rev you read (default: read it now)")


def add_idem(p: argparse.ArgumentParser) -> None:
    p.add_argument("--idem", help="idempotency key (default: derived from the request)")
