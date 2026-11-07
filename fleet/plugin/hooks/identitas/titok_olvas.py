"""Melyik Bash-parancs OLVAS titkot (a titok-kapu, titok_kapu.py). A vedett.py szóelemzője,
de olvasásra: átirányítás, cp/ln/rsync/tar, értelmező -c/heredoc, $(…)/`…`/<(…), for-ciklus,
xargs, plusz a környezet kiírása (env, printenv, ps e, show-environment, /proc/*/environ).

    bash(cmd, cwd, lel) -> ok-szöveg | None

A korábban adott értéket behelyettesíti (`F=út; cat "$F"`), a `dd if=` forrását is nézi; páratlan
idézőjelnél (`echo don't`) szóközös bontással dönt, nem tilt magától. Ami csak listáz (ls, stat, fleet …), szabad; de ha ugyanabban a sorban egy olvasó parancs
változón ($f) vagy xargs-on át kapja a listázott titkot, az tilt.
"""
import os
import re

from bash_szavak import subst, tokens
from titok_kod import PROC, code, envdump, search_args
from titok_minta import secret
from vedett import HEREDOC, INTERP, PREFIX, SEP, SHELLS

LISTERS = {"ls", "stat", "test", "[", "echo", "printf", "realpath", "readlink", "basename", "dirname", "du",
           "wc", "file", "find", "for", "tree"}
NOREAD = {"fleet", "mkdir", "true", "false", "cd", "pwd", "which", "type", "chmod", "touch", "date", "sleep",
          "exit", "unset", "trap", "wait", "kill", "pkill", "jobs"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}", "done", "fi"}
GIT_SAFE = {"add", "rm", "mv", "status", "commit", "push", "pull", "fetch", "checkout", "switch", "branch",
            "merge", "rebase", "ls-files", "check-ignore", "worktree", "stash", "tag", "remote", "config",
            "init", "clone", "reset", "restore", "cherry-pick", "revert", "rev-parse", "log"}
RECURSIVE = {"find", "rsync", "tar", "zip", "rg", "ag", "7z", "tree", "scp"}
FLAG_REC = {"grep", "egrep", "fgrep", "cp", "ls", "chmod", "zgrep"}


def _subs(cmd):
    """$(…), <(…), >(…) és `…` belseje, egymásba ágyazva is."""
    out, i = [], 0
    while i < len(cmd):
        if cmd[i] in "$<>" and cmd[i + 1:i + 2] == "(":
            depth, j = 1, i + 2
            while j < len(cmd) and depth:
                depth += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            out.append(cmd[i + 2:j - 1])
            i = j
        elif cmd[i] == "`":
            j = cmd.find("`", i + 1)
            out.append(cmd[i + 1:j] if j > 0 else cmd[i + 1:])
            i = j + 1 if j > 0 else len(cmd)
        else:
            i += 1
    return out


def _rec(name, args):
    return name in RECURSIVE or name in FLAG_REC and any(
        a in ("--recursive", "--archive") or (a[:1] == "-" and a[1:2] != "-" and set("rRa") & set(a[1:]))
        for a in args)


def _paths(args):
    for a in args:
        if a.startswith("--") and "=" in a:
            a = a.split("=", 1)[1]
        elif a.startswith("-") or re.match(r"^\w+=", a):
            continue
        a = a.lstrip("@")
        if a and ("/" in a or a.startswith((".", "~")) or "*" in a or os.path.lexists(a)):
            yield a


def _command(words, cwd, lel, state):
    while words and (words[0] in KEYWORDS or re.match(r"^\w+=", words[0])):
        words = words[1:]
    if not words:
        return None
    name, args = os.path.basename(words[0]), words[1:]
    if name == "dd":
        args = [a[3:] for a in args if a.startswith("if=")]
    args = search_args(name, args)  # grep MINTA nem út
    why = envdump(name, args)
    if why:
        return why
    if name == "xargs":
        state["var_reader"] = True
    if name in PREFIX and args:
        return _command(args, cwd, lel, state)
    if name in ("ssh", "mosh"):
        return None
    if name in SHELLS | {"eval"}:
        body = args[args.index("-c") + 1] if "-c" in args and args.index("-c") + 1 < len(args) else \
            " ".join(args) if name == "eval" else None
        if body is not None:
            return bash(body, cwd, lel)
    if name in INTERP or name.startswith("python"):
        flag = next((i for i, a in enumerate(args) if a in ("-c", "-e")), None)
        if flag is not None and flag + 1 < len(args):
            return code(args[flag + 1], cwd, lel)
    if name == "git":
        sub = next((a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] != "-C")), "")
        if sub in GIT_SAFE and not (sub == "log" and any(a in ("-p", "--patch") or a.startswith("-L") for a in args)):
            return None
    if name in NOREAD:
        return None
    rec = _rec(name, args)
    lister = name in LISTERS and "-exec" not in args and "-execdir" not in args
    for p in _paths(args[2:] if name == "for" else args):
        why = secret(p, cwd, lel, rec)
        if why and not lister:
            return "%s: %s" % (why, os.path.basename(p.rstrip("/")) or p)
        if why:
            state["listed"] = state.get("listed") or "%s: %s" % (why, os.path.basename(p.rstrip("/")))
    if not lister and (name == "xargs" or any("$" in a for a in args)):
        state["var_reader"] = True
    return None


def bash(cmd, cwd, lel, state=None):
    state = {} if state is None else state
    cmd = subst(cmd)  # `F=~/.config/x/x.env; cat "$F"`
    if PROC.search(cmd):
        return "környezet kiírása (/proc/*/environ)"
    for inner in _subs(cmd):
        why = bash(inner, cwd, lel, state)
        if why:
            return why
    lines, kept, i = cmd.split("\n"), [], 0
    while i < len(lines):
        kept.append(lines[i])
        m = HEREDOC.search(lines[i])
        if m:
            first = os.path.basename((lines[i].split() or [""])[0])
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            body = "\n".join(lines[i + 1:j])
            why = code(body, cwd, lel) if first in INTERP or first.startswith("python") else \
                bash(body, cwd, lel, state) if first in SHELLS else None
            if why:
                return why
            i = j
        i += 1
    toks = tokens(" ; ".join(kept))  # páratlan idézőjel: szóközös bontás, csak valódi találat tilt
    words, k = [], 0
    while k <= len(toks):
        tok = toks[k] if k < len(toks) else ";"
        if tok[:1] in "<>" or tok in ("&>", "&>>"):
            target = toks[k + 1] if k + 1 < len(toks) and not tok.endswith("&") and tok not in ("<<", "<<<") else None
            why = secret(target, cwd, lel) if target and not target.startswith("(") else None
            if why:
                return "%s: %s" % (why, os.path.basename(target))
            k += 2
        elif tok in SEP:
            why = _command(words, cwd, lel, state) if words else None
            if why:
                return why
            words, k = [], k + 1
        else:
            words.append(tok)
            k += 1
    if state.get("listed") and state.get("var_reader"):
        return "listázott titok egy olvasó parancsnak átadva (%s)" % state["listed"]
    return None
