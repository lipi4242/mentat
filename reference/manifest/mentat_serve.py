#!/usr/bin/env python3
"""mentat_serve.py — a local page, form or dev server that never blocks the turn.

    python3 .mentat/bin/mentat_serve.py start NAME --dir FOLDER            [--minutes 60]
    python3 .mentat/bin/mentat_serve.py start NAME --secret VAR [--env .env] [--label TEXT]
    python3 .mentat/bin/mentat_serve.py start NAME [--port 5173 [--path /]] -- <command…>
    python3 .mentat/bin/mentat_serve.py status [NAME]
    python3 .mentat/bin/mentat_serve.py stop NAME | --all

`start` runs it detached (its own session, output in a log), on 127.0.0.1, stops it by itself
after --minutes (0 = only `stop` ends it), waits until the address answers and prints
`URL <address>` — give that to the USER (a command without --port: `RUNNING`, its log) — or `NOT STARTED <why>` and the log's tail (exit 1).
It returns at once. --secret: a one-time form with a hidden field; the value goes to VAR=… in a
git-ignored env file (0600), never to the output or the log; the form closes after one save,
and `status` says `received`. State and log: .mentat/state/serve/NAME.json, NAME.log.
"""
import argparse
import json
import os
import pathlib
import re
import secrets
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted module here cannot shadow the stdlib
from mentat_serve_proc import STATE, _kill, _load, _tail, alive, private, status, stop  # noqa: E402
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def _ignored(root, rel):
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", rel], capture_output=True)
    inside = subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode == 0
    return r.returncode == 0 or not inside


def _refuse(why):
    print("NOT STARTED " + why)
    return 1


def start(root, a):
    if not NAME.match(a.name):
        return _refuse("NAME: lowercase letters, digits and - only")
    d = root / STATE
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    path, log = d / (a.name + ".json"), d / (a.name + ".log")
    if alive(_load(path)):
        return _refuse("%s is already running: %s (stop it first)" % (a.name, _load(path).get("url")))
    st = {"name": a.name, "state": str(path.resolve()), "root": str(root), "host": "127.0.0.1",
          "deadline": time.time() + a.seconds if a.seconds else (time.time() + a.minutes * 60 if a.minutes else 0)}
    if a.command:
        st.update(mode="command", command=a.command, port=a.port, path=a.path)
    elif a.secret:
        env = (root / a.env).resolve()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", a.secret) or root.resolve() not in env.parents:
            return _refuse("--secret takes a variable name, and --env a file inside this folder")
        if not _ignored(root, os.path.relpath(env, root.resolve())):
            return _refuse("%s is not git-ignored: add it to .gitignore first" % a.env)
        st.update(mode="secret", var=a.secret, env=str(env), label=a.label or a.secret,
                  token=secrets.token_urlsafe(16), received=False)
    elif a.dir:
        folder = (root / a.dir).resolve()
        if not folder.is_dir() or not (folder == root.resolve() or root.resolve() in folder.parents):
            return _refuse("--dir takes a folder inside this one")
        st.update(mode="dir", dir=str((root / a.dir).resolve()))
    else:
        return _refuse("give --dir, --secret or a command after --")
    if path.exists():
        path.unlink()
    private(str(path), json.dumps(st))
    kw = ({"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True})
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab") as out:
        p = subprocess.Popen([sys.executable, "-I", str(HERE / "mentat_serve_run.py"), str(path.resolve())],
                             cwd=str(root), stdin=subprocess.DEVNULL, stdout=out, stderr=out, **kw)
    return _probe(path, log, p, a.wait)


def _probe(path, log, p, wait):
    import mentat_web
    end = time.time() + wait
    while time.time() < end:
        st = _load(path)
        if p.poll() is not None:
            break
        if st.get("pid") and not st.get("port") and time.time() > end - wait + 2:  # no address: alive 2 s
            print("RUNNING %s (pid %d, no address; log: %s; stop: mentat_serve.py stop %s)" % (st["name"], p.pid, log, st["name"]))
            return 0
        if st.get("url") and mentat_web.fetch(st["url"], {"User-Agent": "mentat-serve"}, timeout=2)[0]:
            print("URL %s" % st["url"])
            left = "until stopped" if not st["deadline"] else "%d min" % round((st["deadline"] - time.time()) / 60)
            print("RUNNING %s (pid %d, stops by itself: %s; stop: mentat_serve.py stop %s)"
                  % (st["name"], p.pid, left, st["name"]))
            if os.environ.get("SSH_CONNECTION"):
                print("NOTE this address opens on this machine only, not on the USER's own device")
            return 0
        time.sleep(0.3)
    _kill(_load(path) | {"pid": p.pid})
    print("NOT STARTED %s: it did not answer within %ds. Log tail:\n%s" % (_load(path).get("name"), wait, _tail(log)))
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_serve.py")
    p.add_argument("--repo", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("name")
    s.add_argument("--dir")
    s.add_argument("--secret", metavar="VAR")
    s.add_argument("--env", default=".env")
    s.add_argument("--label")
    s.add_argument("--port", type=int)
    s.add_argument("--path", default="/")
    s.add_argument("--minutes", type=int, default=60, help="0 = until stop")
    s.add_argument("--seconds", type=int, default=0, help=argparse.SUPPRESS)
    s.add_argument("--wait", type=int, default=30, help="seconds to wait for the address")
    for n in ("status", "stop"):
        x = sub.add_parser(n)
        x.add_argument("name", nargs="?")
        if n == "stop":
            x.add_argument("--all", action="store_true")
    argv = list(sys.argv[1:] if argv is None else argv)
    cut = argv.index("--") if "--" in argv else len(argv)
    a = p.parse_args(argv[:cut])
    root = pathlib.Path(a.repo)
    if a.cmd == "start":
        a.command = argv[cut + 1:]
        return start(root, a)
    if a.cmd == "stop" and not (a.name or a.all):
        p.error("stop NAME or --all")
    return status(root, a.name) if a.cmd == "status" else stop(root, a.name)


if __name__ == "__main__":
    sys.exit(main())
