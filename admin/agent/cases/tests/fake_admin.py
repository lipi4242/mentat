"""An in-memory stand-in for the admin's cases API (worker/src/plugins/cases),
with the same paths, header, status codes and response shapes — and fault
injection, so the CLI can be tested against an admin that dies or loses a
response. The real API is exercised end to end in the acceptance box run.
"""
import hashlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cases_cli"))
import occurrence as moved  # noqa: E402
import recurrence as rec  # noqa: E402

TOKEN = "test-token-not-a-secret"
COLS = ("title", "description", "status", "next_action", "due_at", "recurrence", "anchor_at",
        "brain_ref", "context", "context_hash", "extra")


class Store:
    def __init__(self):
        self.cases, self.occ, self.events = {}, {}, []
        self.own = []             # GET /api/meta fields.cases — the instance's own fields
        self.faults = []          # [(method, path_prefix, mode)]; mode: "500" | "lost"

    def event(self, cid, kind, body, actor="agent"):
        self.events.append({"id": len(self.events) + 1, "case_id": cid, "at": "2026-10-15 08:00:00",
                            "actor": actor, "actor_token_id": "tok1" if actor == "agent" else None,
                            "kind": kind, "body": json.dumps(body)})

    def detail(self, cid):
        row = self.cases[cid]
        return {**row, "occurrences": sorted(self.occ[cid], key=lambda o: o["due_at"]),
                "open_occurrences": [], "events": []}

    def put(self, cid, body):
        cols = COLS + tuple(f["name"] for f in self.own)
        if set(body) - set(cols) - {"occurrences", "version", "case_id"}:
            return 422, {"error": "unknown field(s): %s" % ", ".join(sorted(set(body) - set(cols)))}
        for f in self.own:
            if f["name"] in body and f.get("options") and body[f["name"]] not in f["options"] + [None]:
                return 422, {"error": "%s must be one of %s" % (f["name"], ", ".join(f["options"]))}
        old = self.cases.get(cid)
        nxt = dict(old) if old else {k: None for k in cols} | {"status": "open", "extra": {}}
        for k in cols:
            if k in body:
                nxt[k] = body[k]
        if "context" in body:
            nxt["context_hash"] = hashlib.sha256(body["context"].encode()).hexdigest() if body["context"] else None
        occ = body.get("occurrences") if not old else self.occ[cid]
        if old and "occurrences" in body and sorted(o["due_at"] for o in body["occurrences"]) != sorted(o["due_at"] for o in occ):
            return 422, {"error": "occurrences cannot be rewritten by PUT"}
        occ = [{"due_at": o["due_at"], "status": o.get("status", "done"), "done_at": o.get("done_at"),
                "note": o.get("note")} for o in occ or []]
        if nxt["recurrence"]:
            last = max((o["due_at"] for o in occ), default=None)
            due = rec.first_open_after(nxt["anchor_at"], nxt["recurrence"], last)
            asked = body["due_at"] if "due_at" in body else (old or {}).get("due_at")
            problem = asked and moved.moved_problem(nxt["anchor_at"], nxt["recurrence"], due, asked)
            if problem and "due_at" in body:
                return 422, {"error": problem}
            nxt["due_at"] = asked if asked and not problem else due
        if not old:
            nxt.update(id=cid, version=1)
            self.cases[cid], self.occ[cid] = nxt, occ
            self.event(cid, "case.created", {"fields": sorted(k for k in body if k in COLS)})
            return 201, self.detail(cid)
        changed = [k for k in cols if nxt.get(k) != old.get(k)]
        if not changed:
            return 200, {**self.detail(cid), "unchanged": True}
        if body.get("version") != old["version"]:
            return 409, {"error": "version conflict", "version": old["version"]}
        nxt["version"] = old["version"] + 1
        self.cases[cid] = nxt
        self.event(cid, "case.updated", {"fields": changed})
        return 200, self.detail(cid)

    def close(self, cid, body):
        row = self.cases.get(cid)
        if not row:
            return 404, {"error": "not found"}
        if not row["recurrence"]:
            return 422, {"error": "not a recurring case"}
        kind, slot = moved.close_slot(row["anchor_at"], row["recurrence"], row["due_at"], body["due_at"],
                                      {o["due_at"] for o in self.occ[cid]})
        if kind == "already":
            return 200, {**self.detail(cid), "already_closed": True}
        if kind == "off":
            return 422, {"error": slot}
        if kind == "later":
            return 409, {"error": "only the earliest open occurrence can be closed", "earliest_open": row["due_at"]}
        body = {**body, "due_at": slot}
        self.occ[cid].append({"due_at": body["due_at"], "status": body.get("status", "done"),
                              "done_at": body.get("done_at"), "note": body.get("note")})
        row.update(due_at=rec.first_open_after(row["anchor_at"], row["recurrence"], body["due_at"]),
                   version=row["version"] + 1)
        self.event(cid, "occurrence.closed", {"due_at": body["due_at"], "next_due_at": row["due_at"]})
        return 200, self.detail(cid)

    def due(self, until):
        items = []
        for row in self.cases.values():
            if row["status"] not in ("open", "waiting") or not row["due_at"] or row["due_at"] > until:
                continue
            dates = moved.open_from(row["anchor_at"], row["recurrence"], row["due_at"], until) if row["recurrence"] else [row["due_at"]]
            items += [{"case_id": row["id"], **{k: row[k] for k in ("title", "status", "description", "next_action",
                       "recurrence", "brain_ref")}, "due_at": d, "closable": i == 0} for i, d in enumerate(dates)]
        return sorted(items, key=lambda i: (i["due_at"], i["title"]))

    def route(self, method, url, body):
        u = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/api/meta":
            return 200, {"fields": {"cases": self.own} if self.own else {}, "entities": []}
        parts = u.path.strip("/").split("/")[2:]   # after api/cases
        if method == "GET" and not parts:
            want = [s for s in q.get("status", "").split(",") if s]
            rows = [{k: v for k, v in r.items() if k != "context"} for r in self.cases.values()
                    if not want or r["status"] in want]
            return 200, sorted(rows, key=lambda r: (r["due_at"] is None, r["due_at"] or "", r["title"]))
        if method == "GET" and parts == ["due"]:
            return 200, self.due(q["until"])
        if method == "GET" and parts == ["events"]:
            after, limit = int(q.get("after", 0)), int(q.get("limit", 100))
            return 200, [e for e in self.events if e["id"] > after][:limit]
        if method == "GET" and len(parts) == 1:
            return (200, self.detail(parts[0])) if parts[0] in self.cases else (404, {"error": "not found"})
        if method == "PUT" and len(parts) == 1:
            return self.put(parts[0], body)
        if method == "POST" and len(parts) == 2 and parts[1] == "occurrences":
            return self.close(parts[0], body)
        return 404, {"error": "no route"}


class _Handler(BaseHTTPRequestHandler):
    def _go(self):
        store = self.server.store
        if self.headers.get("X-Mentat-Token") != TOKEN:
            return self._send(401, {"error": "unauthorized"})
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        mode = next((f for f in store.faults if f[0] == self.command and self.path.startswith(f[1])), None)
        if mode and mode[2] == "500":
            store.faults.remove(mode)
            return self._send(500, {"error": "boom"})
        status, out = store.route(self.command, self.path, body)
        if mode and mode[2] == "lost":       # applied, but the answer never arrives
            store.faults.remove(mode)
            return self._send(502, {"error": "lost"})
        self._send(status, out)

    do_GET = do_PUT = do_POST = _go

    def _send(self, status, out):
        data = json.dumps(out).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def start():
    srv = ThreadingHTTPServer(("localhost", 0), _Handler)
    srv.store = Store()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
