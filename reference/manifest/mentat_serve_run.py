#!/usr/bin/env python3
"""The detached side of mentat_serve.py (it starts this; not for direct use).

    python3 -I mentat_serve_run.py <state file>

Writes its pid, port and URL into the state file, serves 127.0.0.1 only and refuses any other
Host header (a web page cannot reach it by a rebound name), and ends at the deadline. Modes:
dir (a static folder), secret (one hidden-field form at a random path; the value goes to
VAR=… in the env file, 0600; then it ends), command (runs it in this session and ends it).
"""
import functools
import html
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.parse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # at the END (python3 -I)
from mentat_serve_proc import private, write_env  # noqa: E402

FORM = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>%s</title><body style='font:16px system-ui;max-width:28em;margin:3em auto;padding:0 1em'>"
        "<h1 style='font-size:1.3em'>%s</h1><form method=post><input type=password name=value "
        "autocomplete=off autofocus required style='width:100%%;font-size:1em;padding:.5em'>"
        "<p><button style='font-size:1em;padding:.5em 1.2em'>Save / Mentés</button></form>"
        "<p style='color:#666'>It stays on this computer. / Csak ezen a gépen marad.</p>")
DONE = "<!doctype html><meta charset=utf-8><p style='font:16px system-ui;margin:3em'>Saved. / Elmentve. ✓"


def save(st, patch):
    st.update(patch)
    private(st["state"], json.dumps(st))


def handler(st, server_box):
    base = http.server.SimpleHTTPRequestHandler

    class H(base):
        def log_message(self, *a):  # nothing about requests in the log (the path holds a token)
            pass

        def _host_ok(self):
            port = self.server.server_address[1]
            if self.headers.get("Host") in ("127.0.0.1:%d" % port, "localhost:%d" % port):
                return True
            self.send_error(403)
            return False

        def _page(self, code, text):
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _inside(self):
            """dir mode: nothing hidden (a dot segment) and nothing that resolves outside the folder."""
            rel = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            real = os.path.realpath(self.translate_path(self.path))
            segs = rel.split("/") + os.path.relpath(real, st["dir"]).split(os.sep)
            if any(s.startswith(".") and s != "." for s in segs if s) or not (
                    real == st["dir"] or real.startswith(st["dir"] + os.sep)):
                self.send_error(404)
                return False
            return True

        def do_HEAD(self):
            if self._host_ok() and (st["mode"] != "dir" or self._inside()):
                return base.do_HEAD(self) if st["mode"] == "dir" else self.send_error(405)

        def do_GET(self):
            if not self._host_ok():
                return
            if st["mode"] != "secret":
                return base.do_GET(self) if self._inside() else None
            if self.path != "/" + st["token"]:
                return self.send_error(404)
            label = html.escape(st["label"])
            self._page(200, FORM % (label, label))

        def do_POST(self):
            if not self._host_ok() or st["mode"] != "secret" or self.path != "/" + st["token"] or st["received"]:
                return self.send_error(404)
            raw = self.rfile.read(max(0, min(int(self.headers.get("Content-Length") or 0), 65536)))
            value = (urllib.parse.parse_qs(raw.decode("utf-8", "replace")).get("value") or [""])[0].strip()
            if not value or any(c in value for c in "\r\n\0"):
                return self._page(400, FORM % ("?", html.escape(st["label"]) + " — one line, not empty"))
            write_env(st["env"], st["var"], value)
            save(st, {"received": True})
            self._page(200, DONE)
            threading.Thread(target=server_box[0].shutdown, daemon=True).start()

    return H


def serve(st):
    box = []
    h = handler(st, box)
    if st["mode"] == "dir":
        h = functools.partial(h, directory=st["dir"])
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    box.append(srv)
    port = srv.server_address[1]
    path = "/" + st["token"] if st["mode"] == "secret" else "/"
    save(st, {"pid": os.getpid(), "port": port, "url": "http://127.0.0.1:%d%s" % (port, path)})
    if st["deadline"]:
        timer = threading.Timer(max(0, st["deadline"] - time.time()), srv.shutdown)
        timer.daemon = True
        timer.start()
    srv.serve_forever()
    srv.server_close()


def command(st):
    url = st["port"] and "http://127.0.0.1:%d%s" % (st["port"], st["path"] if st["path"].startswith("/") else "/" + st["path"])
    save(st, {"pid": os.getpid(), "url": url})
    env = dict(os.environ, PYTHONUNBUFFERED="1")  # a Python app's output reaches the log at once
    p = subprocess.Popen(st["command"], cwd=st["root"], stdin=subprocess.DEVNULL, env=env)
    try:
        p.wait(timeout=max(1, st["deadline"] - time.time()) if st["deadline"] else None)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def main(argv):
    st = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    print("%s start %s (%s)" % (time.strftime("%Y-%m-%d %H:%M:%S"), st["name"], st["mode"]), flush=True)
    command(st) if st["mode"] == "command" else serve(st)
    print("%s end %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), st["name"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
