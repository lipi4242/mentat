"""cases.backend: admin — the admin API is the record.

Where: `.mentat/local.json` admin.url + admin.token_env (written by the
admin's `npm run connect`); the token from that environment variable or the
repo's `.env`. Not connected, unreachable or refusing -> Unavailable: there is
no fall-back to the markdown files (mentat.json rule 4).
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import fmwrite
import mdstore
import mentat_manifest as mm
import series
from common import CasesError, NotFound, Unavailable, case, ulid

TIMEOUT_S = 15


def _dotenv(path, key):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        k, sep, v = line.strip().removeprefix("export ").partition("=")
        if sep and k.strip() == key:
            return v.strip().strip("\"'") or None
    return None


class Admin:
    name = "admin"

    def __init__(self, root, brain):
        self.root, self.brain = Path(root), brain
        conf = (mm.local(self.root) or {}).get("admin") or {}
        self.url, env = conf.get("url"), conf.get("token_env")
        if not self.url or not env:
            raise Unavailable("admin unavailable: not connected — cases.backend is admin, but no admin is bound "
                              "(.mentat/local.json admin.url + token_env; `npm run connect` in admin/worker of the Mentat clone)")
        self.token = os.environ.get(env) or _dotenv(self.root / ".env", env)
        if not self.token:
            raise Unavailable("admin unavailable: token missing — $%s is not set (env or .env)" % env)

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url.rstrip("/") + path, data=data, method=method, headers={
            "X-Mentat-Token": self.token, "Accept": "application/json", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or e.code >= 500:
                raise Unavailable("admin unavailable: HTTP %d on %s %s" % (e.code, method, path)) from None
            try:
                return e.code, json.load(e)
            except ValueError:
                return e.code, {"error": "HTTP %d" % e.code}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise Unavailable("admin unavailable: %s" % e) from None

    def own_fields(self):
        """The admin's own case fields (GET /api/meta fields.cases), migrated ones only.
        An admin without /api/meta (older than the extension) declares none."""
        if not hasattr(self, "_own"):
            status, out = self.call("GET", "/api/meta")
            fields = ((out.get("fields") or {}).get("cases") or []) if status == 200 and isinstance(out, dict) else []
            self._own = [f for f in fields if isinstance(f, dict) and f.get("name")]
        return self._own

    def own(self):
        return tuple(f["name"] for f in self.own_fields() if not f.get("pending"))

    def _ok(self, status, out):
        if status >= 400:
            raise CasesError(out.get("error", "HTTP %d" % status)
                             + (": %s" % out["earliest_open"] if "earliest_open" in out else ""))
        return out

    def raw(self, cid):
        status, out = self.call("GET", "/api/cases/" + quote(cid))
        if status == 404:
            raise NotFound("no case %s" % cid)
        return self._ok(status, out)

    def list_raw(self, want):
        return self._ok(*self.call("GET", "/api/cases?status=" + ",".join(want)))

    def list(self, want):
        own = self.own()
        return [case(r, own) for r in self.list_raw(want)]

    def due(self, until):
        items = self._ok(*self.call("GET", "/api/cases/due?until=" + until))
        return series.sort_items([series.item(i) for i in items])

    def get(self, cid):
        r = self.raw(cid)
        c = case(r, self.own())
        path = self.root / (r.get("brain_ref") or "-")
        c["context"] = fmwrite.context(path.read_text(encoding="utf-8")) if path.is_file() else (r.get("context") or "")
        c["version"] = r["version"]
        return c

    def put(self, cid, fields, file=None, title=None):
        """Create (cid None: a new id, a brain file with case_id) or update."""
        if cid is None:
            md = mdstore.Markdown(self.root, self.brain)
            path = Path(file) if file else md._new_path(title or fields.get("title") or "")
            cid = ulid()
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            mdstore.write(path, fmwrite.set_fields(text, {"type": "case", "case_id": cid}))
            fields = {**fields, "brain_ref": path.resolve().relative_to(self.root.resolve()).as_posix()}
        self.put_raw(cid, fields)
        return self.get(cid)

    def put_raw(self, cid, fields):
        """PUT keyed by the writer's id; a 409 re-reads and re-applies once."""
        for _ in range(2):
            try:
                body = {**{k: v for k, v in fields.items() if k != "occurrences"}, "version": self.raw(cid)["version"]}
            except NotFound:
                body = dict(fields)
            status, out = self.call("PUT", "/api/cases/" + quote(cid), body)
            if status != 409:
                return self._ok(status, out)
        raise CasesError("the case keeps changing under us (409) — re-read and retry")

    def close(self, cid, day=None, status="done", done_at=None, note=None):
        r = self.raw(cid)
        if not r.get("recurrence"):
            if r["status"] not in ("open", "waiting"):
                return self.get(cid), True
            self.put_raw(cid, {"status": "done"})
            return self.get(cid), False
        body = {"due_at": day or r["due_at"], "status": status, "done_at": done_at, "note": note}
        out = self._ok(*self.call("POST", "/api/cases/%s/occurrences" % quote(cid),
                                  {k: v for k, v in body.items() if v is not None}))
        return self.get(cid), bool(out.get("already_closed"))
