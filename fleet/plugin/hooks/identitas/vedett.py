"""Which tool call WRITES one of the identity gate's own files (F-41). Reading, running and a
command that runs on another machine are free.

    protected_write(tool, inp, cwd) -> path | "beallitas:<path>" | None

Protected, as resolved absolute paths: all of `~/.mentat/bin/` (the gate's and nemakad's code),
and `~/.mentat/identitas.txt`, `elsofel.txt`, `identitas-cache.json`. A repo's own relative
`.mentat/bin` is not the gate's. The settings answer (`beallitas:`, the hook asks) is only for the
user's Claude roots: `~/.claude*/settings(.local).json` and `$CLAUDE_CONFIG_DIR/` — never a repo's
own `.claude/settings.json`. Bash is read word by word: a redirect target or a writing command's
path argument counts; the text of `ssh host '…'`, of a commit message or of a heredoc fed to a
non-interpreter does not. Code given to an interpreter (`-c`, `-e`, a heredoc) counts when it
names a protected file and writes. Unparseable shell text falls back to the old, wider check.
"""
import os
import re
import shlex

from vedett_ut import _code, _copy, _hit, _home, sed_files

WRITERS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
ANCESTOR = {"rm", "rmdir", "unlink", "shred", "mv"}  # deletes or moves: an ancestor folder counts too
COPY = {"cp", "install", "ln", "scp", "rsync"}  # the last path is written; the sources are read
PATHWRITE = ANCESTOR | COPY | {"chmod", "chown", "chflags", "truncate", "touch", "tee", "dd"}
FIND_EXEC = ("-exec", "-execdir", "-ok", "-okdir")
FIND_OUT = ("-fprint", "-fprint0", "-fprintf", "-fls")
INPLACE = {"sed", "perl", "gsed"}
INTERP = {"python", "python3", "node", "perl", "ruby"}
SHELLS = {"sh", "bash", "zsh", "dash"}
PREFIX = {"sudo", "env", "command", "nice", "nohup", "time", "exec", "xargs", "caffeinate"}
SEP = {";", "&&", "||", "|", "&", "(", ")"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def _command(words, cwd):
    while words and (re.match(r"^\w+=", words[0]) or os.path.basename(words[0]) in PREFIX):
        words = words[1:]
    if not words:
        return None
    name, args = os.path.basename(words[0]), words[1:]
    if name in ("ssh", "mosh") or name == "git" and "-C" not in args:
        return None  # another machine; a commit message is text
    if name == "git":
        i = args.index("-C") + 1  # only `git clean` deletes; the rest writes the work tree itself
        return _hit(args[i], cwd, "clean" in args) if i < len(args) and \
            any(a in args for a in ("checkout", "reset", "clean", "restore", "rm", "mv", "apply", "pull")) else None
    if name in SHELLS and "-c" in args and args.index("-c") + 1 < len(args):
        return bash(args[args.index("-c") + 1], cwd)
    if name in INTERP:
        flag = next((i for i, a in enumerate(args) if a in ("-c", "-e")), None)
        return _code(args[flag + 1], cwd) if flag is not None and flag + 1 < len(args) else None
    if name == "find":
        return _find(args, cwd)
    if name in INPLACE and not any(a.startswith("-i") or a == "-pi" for a in args):
        return None
    if name in PATHWRITE | INPLACE:
        paths = [a[3:] if a.startswith("of=") else a for a in args
                 if (not a.startswith("-") or a.startswith("of=")) and not re.match(r"^[\w.-]+:", a) and a]
        paths = sed_files(args) if name in INPLACE else [a[3:] for a in args if a.startswith("of=")] \
            if name == "dd" else paths
        if name in COPY | {"mv"} and paths:
            return _copy(name, paths, args, cwd)
        for p in paths:
            hit = _hit(p, cwd, name in ANCESTOR)
            if hit:
                return hit
    return None


def _find(args, cwd):
    """`find` only reads, unless it deletes (-delete), runs a writing command (-exec/-ok …) or
    writes its list to a file (-fprint …). Its starting points count as an ancestor only then."""
    roots = []
    for a in args:
        if a.startswith("-") or a in ("(", "!", ")"):
            break
        roots.append(a)
    for i, a in enumerate(args):
        if a in FIND_OUT and i + 1 < len(args):
            hit = _hit(args[i + 1], cwd)
            if hit:
                return hit
        if a in FIND_EXEC:
            end = next((j for j in range(i + 1, len(args)) if args[j] in (";", "+")), len(args))
            inner = [x for x in args[i + 1:end] if x != "{}"]
            if inner and os.path.basename(inner[0]) in ANCESTOR:
                hit = next((h for h in (_hit(r, cwd, True) for r in roots) if h), None)
                if hit:
                    return hit
            hit = _command(inner, cwd) if inner else None
            if hit:
                return hit
    if "-delete" in args:
        return next((h for h in (_hit(r, cwd, True) for r in roots) if h), None)
    return None


def bash(cmd, cwd):
    lines, body_hits = cmd.split("\n"), []
    i, kept = 0, []
    while i < len(lines):
        kept.append(lines[i])
        m = HEREDOC.search(lines[i])
        if m:
            first = os.path.basename((lines[i].split() or [""])[0])
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            body = "\n".join(lines[i + 1:j])
            body_hits.append(_code(body, cwd) if first in INTERP else bash(body, cwd) if first in SHELLS else None)
            i = j
        i += 1
    if any(body_hits):
        return next(h for h in body_hits if h)
    try:
        lex = shlex.shlex(" ; ".join(kept), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:  # unbalanced quotes: the old, wider rule
        return os.path.join(_home(), ".mentat") if ".mentat" in cmd and re.search(r">|\brm\b|\bmv\b", cmd) else None
    words, k = [], 0
    while k <= len(toks):
        tok = toks[k] if k < len(toks) else ";"
        if tok.startswith(">") or tok in ("&>", "&>>"):
            target = toks[k + 1] if k + 1 < len(toks) and not tok.endswith("&") else None
            hit = _hit(target, cwd) if target else None
            if hit:
                return hit
            k += 2
        elif tok.startswith("<"):
            k += 2  # input: reading
        elif tok in SEP:
            hit = _command(words, cwd) if words else None
            if hit:
                return hit
            words, k = [], k + 1
        else:
            words.append(tok)
            k += 1
    return None


def protected_write(tool, inp, cwd=None):
    inp = inp or {}
    if tool in WRITERS:
        p = str(inp.get("file_path") or inp.get("notebook_path") or "")
        return _hit(p, cwd) if p else None
    if tool == "Bash":
        return bash(str(inp.get("command", "")), cwd)
    return None
