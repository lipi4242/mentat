"""A local stand-in for the Google APIs (tests only): Calendar, Gmail, Drive, Sheets, the token
endpoint, in memory. Every request is recorded in `calls` as (method, path, query, body)."""
import base64
import email
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GOOD = ("a-good", "a-new")  # the token in token.json, the one a refresh returns


class Fake:
    def __init__(self, me="me@example.com"):
        self.me, self.events, self.messages, self.values, self.calls = me, {}, {}, {}, []
        self.perms = {"f1": [{"type": "user", "role": "owner", "emailAddress": me}]}
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, doc):
                body = json.dumps(doc).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def _handle(self, method):
                u = urllib.parse.urlsplit(self.path)
                q = dict(urllib.parse.parse_qsl(u.query))
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
                if u.path == "/token":
                    form = dict(urllib.parse.parse_qsl(raw))
                    fake.calls.append((method, u.path, q, form))
                    return self._send(200, {"access_token": GOOD[1], "expires_in": 3600})
                body = json.loads(raw) if raw else None
                fake.calls.append((method, u.path, q, body))
                if self.headers.get("Authorization") not in ["Bearer " + t for t in GOOD]:
                    return self._send(401, {"error": {"code": 401, "message": "invalid credentials"}})
                code, doc = fake.route(method, u.path, q, body)
                return self._send(code, doc)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PATCH(self):
                self._handle("PATCH")

            def do_PUT(self):
                self._handle("PUT")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def writes(self):
        return [c for c in self.calls if c[0] != "GET" and c[1] != "/token"]

    def route(self, method, path, q, body):
        m = re.match(r"/calendar/v3/calendars/[^/]+/events(?:/([^/]+))?$", path)
        if m:
            eid = m.group(1)
            if method == "POST":
                eid = "e%d" % (len(self.events) + 1)
                self.events[eid] = dict(body, id=eid, organizer={"email": self.me})
            elif method == "PATCH":
                self.events[eid].update(body)
            return (200, self.events[eid]) if eid in self.events else (404, {})
        if path == "/gmail/v1/users/me/profile":
            return 200, {"emailAddress": self.me}
        if path == "/gmail/v1/users/me/messages/send":
            mid = "m%d" % (len(self.messages) + 1)
            self.messages[mid] = email.message_from_bytes(base64.urlsafe_b64decode(body["raw"]))
            return 200, {"id": mid}
        m = re.match(r"/gmail/v1/users/me/messages/([^/]+)$", path)
        if m:
            msg = self.messages[m.group(1)]
            return 200, {"payload": {"headers": [{"name": k, "value": v} for k, v in msg.items()]}}
        m = re.match(r"/drive/v3/files/([^/]+)/permissions$", path)
        if m:
            perms = self.perms.setdefault(m.group(1), [])
            if method == "POST":
                perms.append(body)
                return 200, dict(body, id="p%d" % len(perms))
            return 200, {"permissions": perms}
        m = re.match(r"/v4/spreadsheets/([^/]+)/values/(.+)$", path)
        if m:
            key = (m.group(1), urllib.parse.unquote(m.group(2)))
            if method == "PUT":
                self.values[key] = body["values"]
                return 200, {"updatedRows": len(body["values"])}
            return 200, {"values": self.values.get(key, [])}
        return 404, {"error": {"code": 404, "message": "no route " + path}}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
