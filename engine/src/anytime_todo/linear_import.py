"""Import a Linear export into the backlog, through the public todo API only.

    python3 -m anytime_todo.linear_import export.json --map map.json [--dry-run]

map.json: {"users": {"<Linear name>": "<handle>"}, "projects": {"KRI": "Thufir backlog"}}.
Per item ONE call (so no half-finished item exists); parents in a second pass. A rerun
sends the same stable keys and the server only fills what is missing (never overwrites).

Server contract: admin/docs/plugins/todo/BACKLOG.md ("Linear import"). Needs a human
session or a token with the scopes `todo:write todo:import`.
    GET  /projects  ·  POST /projects {prefix, name, idem_key}
    POST /items/import {<item_payload>}  -> 201 {id, key, created:true, added} | 200 on a rerun
    POST /items/import/parent {ext_ref, parent_ext_ref}   (fill-only)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .api import Client, TodoApiError
from .linear_parse import ImportError_, item_payload


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def started_at(state_file: Path, now: str | None = None) -> str:
    """import_started_at is recorded once, then reused by every rerun."""
    try:
        return json.loads(state_file.read_text())["import_started_at"]
    except (OSError, ValueError, KeyError):
        ts = now or _now()
        state_file.write_text(json.dumps({"import_started_at": ts}))
        return ts


def plan(export: dict, users: dict, started: str) -> list[dict]:
    if not export.get("complete"):
        raise ImportError_("the export is incomplete; re-run linear_export first")
    rows = sorted(export["issues"], key=lambda r: (r["identifier"].rpartition("-")[0],
                                                   int(r["identifier"].rpartition("-")[2])))
    return [dict(item_payload(r, users, started), _parent=r.get("parent")) for r in rows]


def summary(items: list[dict]) -> str:
    c = Counter(i["stage"] for i in items)
    return (f"{len(items)} items " + " ".join(f"{k}={v}" for k, v in sorted(c.items()))
            + f" | archived={sum(i['archived'] for i in items)}"
            f" acs={sum(len(i['acs']) for i in items)}"
            f" comments={sum(len(i['comments']) for i in items)}"
            f" pr_links={sum(len(i['links']) for i in items)}")


_WHY = {403: "an import-capable token is needed (scopes `todo:write todo:import`)",
        409: "the number is already taken: an item created in Mentat uses it",
        422: "the server refused this item's stage or developer",
        404: "the parent or the item is not imported yet"}


def _call(client, method, path, body=None, what=""):
    try:
        return client._call(method, path, body)
    except TodoApiError as e:
        why = _WHY.get(e.status)
        if why:
            raise ImportError_(f"{what or path}: {why} (HTTP {e.status})") from None
        raise


def run(client, items: list[dict], projects: dict) -> dict:
    have = {p["prefix"] for p in _call(client, "GET", "/projects")}
    for prefix in sorted({i["project"] for i in items} - have):
        _call(client, "POST", "/projects", {"prefix": prefix, "name": projects.get(prefix, prefix),
                                            "idem_key": f"linear-import:project:{prefix}"}, f"project {prefix}")
    created = filled = 0
    by_uuid = {i["ext_ref"]: i for i in items}
    for it in items:
        body = {k: v for k, v in it.items() if not k.startswith("_")}
        r = _call(client, "POST", "/items/import", body, f"{it['project']}-{it['number']}")
        created += bool(r.get("created"))
        filled += not r.get("created")
    for it in items:
        if it["_parent"] and f"linear:{it['_parent']}" in by_uuid:
            _call(client, "POST", "/items/import/parent",
                  {"ext_ref": it["ext_ref"], "parent_ext_ref": f"linear:{it['_parent']}"},
                  f"parent of {it['project']}-{it['number']}")
    return {"created": created, "existing": filled}


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(prog="import-linear")
    ap.add_argument("export")
    ap.add_argument("--map", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--started-at", help="override import_started_at (tests)")
    a = ap.parse_args(argv)
    try:
        export = json.loads(Path(a.export).read_text())
        mp = json.loads(Path(a.map).read_text())
        if a.dry_run:                 # a dry run must not write even the state file
            started = a.started_at or _now()
        else:
            started = started_at(Path(a.export + ".import.json"), a.started_at)
        items = plan(export, mp.get("users", {}), started)
        print(summary(items))
        if a.dry_run:
            return 0
        if client is None:
            from . import settings
            from anytime_engine import config
            s = settings.load(config.repo_root().resolve())
            if s is None:
                print("the todo pack is not configured (TODO_API + TODO_HANDLE)", file=sys.stderr)
                return 2
            client = Client(s.api, s.token())
        print(json.dumps(run(client, items, mp.get("projects", {}))))
        return 0
    except (ImportError_, TodoApiError, OSError, ValueError, KeyError) as e:
        print(f"import-linear: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
