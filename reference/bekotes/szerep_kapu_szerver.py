"""A server, or any foreground command that never returns (szerep_kapu_fut), started from the
Bash tool (for szerep_dontes): it would block the turn.

blocks(tool, inp, cwd) -> True: a simple command starts a web or dev server — in the foreground
it never returns, with run_in_background it is killed at the tool's time limit or outlives the
session unseen. szerep_dontes denies it in both modes with the command that works:
`mentat_serve.py start` (detached, bounded lifetime, probed, prints the URL). The tool's own
command line is open, whatever it wraps after `--`. Builds and tests stay open.
Known limits: a net, not the process — a server started from a script file (`node server.js`),
or a name this list does not know, is not seen; a package script is judged by its text in
package.json, and is open when that cannot be read or decided (a workspace --filter).
"""
import json
import os
import re

import szerep_kapu_fut as fut
from szerep_bash import PREFIX, commands

PY_MODULES = {"http.server", "SimpleHTTPServer", "uvicorn", "gunicorn", "hypercorn", "streamlit"}
ALWAYS = {"http-server", "serve", "live-server", "uvicorn", "gunicorn", "hypercorn"}
SUBCMD = {"flask": {"run"}, "streamlit": {"run"}, "hugo": {"server", "serve"}, "jekyll": {"serve", "s"},
          "vite": {"", "dev", "serve", "preview"}, "next": {"dev", "start"}, "nuxt": {"dev", "preview"},
          "astro": {"dev", "preview"}, "ng": {"serve"}, "caddy": {"run", "file-server"},
          "busybox": {"httpd"}, "wrangler": {"dev", "pages"}}
RUNNERS = {"npm", "pnpm", "yarn", "bun"}
LAUNCH = {"npx", "pnpx", "bunx"}
WRAP = {"setsid", "stdbuf", "caffeinate", "bundle"}
RUN = {"uv", "poetry", "pipenv", "pdm", "hatch", "rye"}  # `<x> run <command>`
VALUED = {"-p", "--port", "--host", "-H", "-C", "--dir", "--prefix", "--filter", "-F", "--cwd", "--config",
          "-c", "--mode", "-n", "-s", "--signal", "-k", "--kill-after", "--bind", "-b", "--directory", "-d"}
INFO = {"--help", "-h", "--version", "-V", "-v"}
TOOL = "mentat_serve.py"


def _plain(words):
    """Drop leading options (and the value of a known valued one)."""
    while words and words[0].startswith("-"):
        words = words[2:] if words[0] in VALUED else words[1:]
    return words


def _positional(args):
    """The non-option words, skipping the value of a known valued option."""
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUED
        else:
            out.append(a)
    return out


def _strip(words):
    """Drop wrappers that only change how it runs: setsid, timeout N, `bundle exec`, npx -y."""
    while words:
        head = os.path.basename(words[0])
        if head.startswith("-"):  # options of a wrapper szerep_bash already dropped (nice -n 10 …)
            words = _plain(words)
        elif head == "timeout":
            words = _plain(words[1:])[1:]  # the duration
        elif head in WRAP or head in PREFIX or (head in RUN and words[1:2] == ["run"]):
            words = words[2:] if words[1:2] in (["exec"], ["run"]) else words[1:]
            words = _plain(words) if words and words[0].startswith("-") else words
        elif head in LAUNCH or (head == "npm" and words[1:2] in (["exec"], ["x"])):
            rest = words[1:] if head in LAUNCH else words[2:]
            while rest and (rest[0].startswith("-") or rest[0] == "--"):
                rest = rest[2:] if rest[0] in ("-p", "--package") else rest[1:]
            words = rest
        else:
            return words
    return words


def _server(words, wd=None, depth=0):
    words = _strip(words)
    if not words:
        return False
    name = re.sub(r"@.*$", "", os.path.basename(words[0]))
    args = words[1:]
    if INFO & set(args):  # --help / --version only print
        return False
    if re.fullmatch(r"python[0-9.]*", name):
        args = [x for a in args for x in (["-m", a[2:]] if a.startswith("-m") and len(a) > 2 else [a])]
        if "-m" in args and args.index("-m") + 1 < len(args):
            mod = args[args.index("-m") + 1]
            return mod in PY_MODULES or (mod == "flask" and "run" in args)
        if any(a.endswith("manage.py") for a in args[:1]) and "runserver" in args:
            return True
    if name == "php":
        return "-S" in args
    if name in ALWAYS:
        return True
    if name in SUBCMD:
        first = (_positional(args) or [""])[0]
        return first in SUBCMD[name] and not (name == "wrangler" and first == "pages" and "dev" not in args)
    if name in RUNNERS:
        return _script(name, args, wd, depth)
    return fut.never_returns(name, args, wd)  # watchers, followers, a script that listens


def _script(runner, args, wd, depth):
    """`npm start` / `pnpm dev` / `npm run x`: a server only if package.json's script is one;
    anything it cannot decide (no package.json, a workspace --filter, no such script) is open."""
    pos = _positional(args)
    name = pos[1] if pos[:1] in (["run"], ["run-script"]) and pos[1:] else (pos[0] if pos else "")
    if not name or depth > 2 or {"--filter", "-F", "--workspace", "-w"} & set(args) or (
            runner == "npm" and pos[:1] not in (["run"], ["run-script"], ["start"])):
        return False
    where = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-C", "--prefix", "--dir", "--cwd")), ".")
    pkg = os.path.join(os.path.expanduser(where) if os.path.isabs(os.path.expanduser(where))
                       else os.path.join(wd or ".", where), "package.json")
    try:
        with open(pkg, encoding="utf-8") as f:
            script = (json.load(f).get("scripts") or {}).get(name)
    except (OSError, ValueError, AttributeError):
        return False
    if not isinstance(script, str):
        return False
    return any(_server(w, os.path.dirname(pkg), depth + 1) for _n, w, _wd, _r, _a in commands(script, os.path.dirname(pkg)))


def blocks(tool, inp, cwd):
    if tool != "Bash":
        return False
    wrapped = None
    for _name, words, _wd, _redir, _assigned in commands(str(inp.get("command", "")), cwd):
        if any(os.path.basename(w) == TOOL for w in words):
            wrapped = tuple(words[words.index("--") + 1:]) if "--" in words else None
            continue
        if wrapped and tuple(words) == wrapped:  # the tool's own `-- <command>`: it runs detached
            wrapped = None
            continue
        if _server(words, _wd):
            return True
    return False
