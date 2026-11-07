#!/usr/bin/env python3
"""mentat_secret.py — a key into the git-ignored env file, and is it there, never shown.

    python3 .mentat/bin/mentat_secret.py put VAR [--env .env]   # the value on stdin (heredoc)
    python3 .mentat/bin/mentat_secret.py has VAR [--env .env]   # SET VAR (n chars) | MISSING VAR

The USER types a key into the hidden form (`mentat_serve.py start NAME --secret VAR`); `put` is
for a key they already pasted into the chat: it goes into the env file (0600, must be
git-ignored) at once, and the output says it should be replaced with a new one, because it was
in the chat. `has` answers without the value. The tools that use the key read it themselves.
This is the route the guard keeps open (it gates reading .env, not these).
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted module here cannot shadow the stdlib
from mentat_serve import _ignored  # noqa: E402
from mentat_serve_proc import write_env  # noqa: E402

VAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _env(root, rel):
    env = (root / rel).resolve()
    if root.resolve() not in env.parents:
        raise SystemExit("NOT SAVED --env must be a file inside this folder")
    if not _ignored(root, str(env.relative_to(root.resolve()))):
        raise SystemExit("NOT SAVED %s is not git-ignored: add it to .gitignore first" % rel)
    return env


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_secret.py")
    p.add_argument("--repo", default=".")
    p.add_argument("cmd", choices=["put", "has"])
    p.add_argument("var")
    p.add_argument("--env", default=".env")
    a = p.parse_args(argv)
    if not VAR.match(a.var):
        print("NOT SAVED the name is a variable name (letters, digits, _)")
        return 1
    root = pathlib.Path(a.repo)
    try:
        env = _env(root, a.env)
    except SystemExit as e:
        print(e)
        return 1
    if a.cmd == "has":
        lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
        got = next((ln.split("=", 1)[1] for ln in lines if ln.startswith(a.var + "=")), "")
        print("SET %s (%d chars) in %s" % (a.var, len(got), a.env) if got else "MISSING %s in %s" % (a.var, a.env))
        return 0 if got else 1
    value = sys.stdin.read().strip()
    if not value or any(c in value for c in "\r\n\0"):
        print("NOT SAVED the value must be one non-empty line on stdin")
        return 1
    write_env(env, a.var, value)
    print("SAVED %s in %s (0600, git-ignored). It was in the chat: tell the USER to make a new one "
          "when they can and put that in with the form (mentat_serve.py --secret)." % (a.var, a.env))
    return 0


if __name__ == "__main__":
    sys.exit(main())
