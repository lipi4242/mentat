"""A local stand-in for the Cloudflare API (tests only): a few endpoints, in memory."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "t-good"


class Fake:
    def __init__(self, perms=("workers", "access", "d1"), apps=None):
        self.perms, self.apps, self.created = set(perms), list(apps or []), []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, result=None, errors=None):
                body = json.dumps({"success": code < 400, "result": result, "errors": errors or []}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def _route(self, method):
                if self.headers.get("Authorization") != "Bearer " + TOKEN:
                    return self._send(401, errors=[{"code": 10001, "message": "Unable to authenticate"}])
                p = self.path
                need = ("workers" if "/workers/" in p else "access" if "/access/" in p
                        else "d1" if "/d1/" in p else "kv" if "/storage/kv/" in p else "r2" if "/r2/" in p
                        else None)
                if need and need not in fake.perms:
                    return self._send(403, errors=[{"code": 10000, "message": "Authentication error"}])
                if p == "/user/tokens/verify":
                    return self._send(200, {"status": "active"})
                if p == "/accounts":
                    return self._send(200, [{"id": "acc1", "name": "A"}])
                if p == "/accounts/acc1/workers/scripts":
                    return self._send(200, [{"id": "lista", "tag": "tag123"}])
                if p in ("/accounts/acc1/d1/database", "/accounts/acc1/storage/kv/namespaces",
                         "/accounts/acc1/r2/buckets"):
                    return self._send(200, [])
                if p == "/accounts/acc1/access/apps" and method == "GET":
                    return self._send(200, fake.apps)
                if p == "/accounts/acc1/access/apps" and method == "POST":
                    n = int(self.headers.get("Content-Length", 0))
                    app = json.loads(self.rfile.read(n))
                    fake.created.append(app)
                    fake.apps.append(app)
                    return self._send(200, app)
                return self._send(404, errors=[{"code": 7003, "message": "no route"}])

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]

    def close(self):
        self.srv.shutdown()
