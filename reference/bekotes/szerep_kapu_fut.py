"""Foreground commands that never return, for szerep_kapu_szerver (same deny, same way out).

never_returns(name, args, wd) -> True: a follower (`tail -f`, `journalctl -f`, `kubectl logs -f`),
a watcher (`watch`, `nodemon`, any `--watch`), a pager/editor/monitor (`less`, `top`, `vim`),
`docker compose up` without -d, `kubectl port-forward`, `ping` without a count, or a script
(node/bun/deno/python FILE) whose text listens on a port. The way out: run it once (`tail -n`,
`ping -c 3`, `up -d`) or start it with `mentat_serve.py start NAME [--port P] -- <command>`.
Known limits: a script is read only when it is a plain file next to the command (no imports
followed); a name this list does not know is not seen.
"""
import os
import re

ALWAYS = {"watch", "nodemon", "watchexec", "entr", "less", "more", "most", "top", "htop", "btop",
          "vim", "vi", "nvim", "nano", "emacs", "man"}
FOLLOW = {"tail", "journalctl"}
LISTENS = re.compile(r"\.listen\(|createServer\(|serve_forever\(|app\.run\(|uvicorn\.run\(|"
                     r"socketserver\.|Deno\.serve\(|Bun\.serve\(|web\.run_app\(|\.serve\(\s*port")
INTERP = re.compile(r"^(node|bun|deno|python[0-9.]*)$")


def _follows(name, args):
    if name == "tail":
        return any(a in ("-f", "-F", "--follow") or a.startswith("--follow=")
                   or (re.fullmatch(r"-[a-zA-Z]+", a) and set(a[1:]) & {"f", "F"}) for a in args)
    return any(a in ("-f", "--follow") for a in args)


def _listens(args, wd):
    script = next((a for a in args if not a.startswith("-") and re.search(r"\.(m?js|cjs|ts|py)$", a)), None)
    if not script:
        return False
    path = script if os.path.isabs(script) else os.path.join(wd or ".", script)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(LISTENS.search(f.read(200_000)))
    except OSError:
        return False


def never_returns(name, args, wd):
    if name in ALWAYS or "--watch" in args or "--watchAll" in args:
        return True
    if name in FOLLOW:
        return _follows(name, args)
    if name == "kubectl":
        return args[:1] == ["port-forward"] or (args[:1] == ["logs"] and _follows(name, args))
    if name in ("docker", "docker-compose", "podman"):
        up = args[:2] == ["compose", "up"] or (name == "docker-compose" and args[:1] == ["up"])
        return up and not {"-d", "--detach"} & set(args)
    if name == "ping":
        return not any(re.match(r"-c\d*$|-n$|--count", a) for a in args)
    if INTERP.match(name):
        return _listens(args, wd)
    return False
