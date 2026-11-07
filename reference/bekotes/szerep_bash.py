"""What a Bash command reads and writes, for szerep_rules.py (Read / Edit / Write rules).

    analyse(cmd, cwd) -> (reads, writes)   absolute paths when cwd is given

Reads: every word with a `/`, a bare word that exists in the segment's cwd, glob
matches, path-like text inside code (`python -c "open('a/b')"`, backticks), and the
segment's own cwd (`ls` inside a forbidden folder). `cd`/`pushd` move that cwd.
Writes: redirect targets, `sed -i`/`perl -i`, `tee`, `rm`, `touch`, `truncate`,
`chmod`, `chown`, `mv` (all arguments), `cp`/`ln`/`install`/`rsync` (the target),
`dd of=`, `curl -o`, `wget -O`, recursively inside `sh|bash|zsh -c` and `eval`.
Not covered (an accident guard, not a security boundary): shell variables
(`D=bank; cat $D/x`), writes made by interpreters (`python -c`, `node -e`), git
commands that rewrite files, and a symlink created in the same command.
"""
import glob
import os
import re
import shlex

WRITE_ALL = {"rm", "rmdir", "touch", "truncate", "tee", "chmod", "chown", "unlink", "shred", "mv"}
WRITE_TARGET = {"cp", "ln", "install", "rsync"}
IN_PLACE = {"sed", "gsed", "perl"}
SHELLS = {"sh", "bash", "zsh", "dash"}
PREFIX = {"env", "sudo", "command", "nohup", "time", "nice", "exec"}
CD = {"cd", "pushd"}
CODE = set("()'\"`=;$")
EMBED = re.compile(r"(?:~|\$\{?HOME\}?)?[\w.@-]*/[\w./@-]*")
ASSIGN = re.compile(r"^[A-Za-z_]\w*=")


def _expand(w):
    home = os.environ.get("HOME", "")
    if home:
        w = re.sub(r"^\$\{?HOME\}?(?=/|$)", home, w)
    return os.path.expanduser(w)


def _tokens(cmd):
    try:
        lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return cmd.split()


def _segments(tokens):
    """[(words, redirect targets)] split on ; && || | & ( )."""
    out, words, redir, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        if t and set(t) <= set("();<>|&"):
            if ">" in t:
                nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
                if nxt and not (nxt.isdigit() or nxt == "-"):
                    redir.append(nxt)
                i += 2
                continue
            if "<" not in t:
                out.append((words, redir))
                words, redir = [], []
        else:
            words.append(t.strip("`"))
        i += 1
    return out + [(words, redir)]


def _join(cwd, w):
    w = _expand(w)
    return os.path.normpath(w if os.path.isabs(w) or not cwd else os.path.join(cwd, w))


def _args(words):
    return [w for w in words[1:] if w and not w.startswith("-")]


def _writes(cmd, words):
    args = _args(words)
    if cmd in WRITE_ALL:
        return args
    if cmd in WRITE_TARGET:
        tgt = [w.split("=", 1)[1] for w in words if w.startswith("--target-directory=")]
        tgt += [words[i + 1] for i, w in enumerate(words[:-1]) if w == "-t"]
        return tgt or args[-1:]
    if cmd in IN_PLACE and any(re.match(r"^-[a-zA-Z]*i|^--in-place", w) for w in words[1:]):
        return args
    if cmd == "dd":
        return [w[3:] for w in words if w.startswith("of=")]
    if cmd in ("curl", "wget"):
        flags = ("-o", "--output") if cmd == "curl" else ("-O", "--output-document")
        return ([words[i + 1] for i, w in enumerate(words[:-1]) if w in flags]
                + [w.split("=", 1)[1] for w in words if w.startswith(flags[1] + "=")])
    return []


def _reads(words, cwd):
    out = []
    for w in words:
        if not w or w.startswith("-"):
            continue
        cands = [w] + ([w.split("=", 1)[1]] if "=" in w else [])
        if CODE & set(w):
            cands += [m for m in EMBED.findall(w) if re.search(r"\w", m)]  # not a bare `/`
        for c in cands:
            p = _join(cwd, c)
            if "/" in c or (cwd and os.path.lexists(p)):
                out.append(p)
            if cwd and set("*?[") & set(c):
                out += glob.glob(p)
    return out


def commands(cmd, cwd=None, depth=0):
    """[(name, words, cwd, redirect targets, path-like VAR=values)] per simple command
    (`D=~/x; cat $D/y` reads ~/x); cd/pushd move cwd; sh -c recursed."""
    out = []
    for words, redir in _segments(_tokens(cmd)):
        assigns = []
        while words and (ASSIGN.match(words[0]) or os.path.basename(words[0]) in PREFIX):
            assigns += [words[0].split("=", 1)[1]] if ASSIGN.match(words[0]) else []
            words = words[1:]
        name = os.path.basename(words[0]) if words else ""
        out.append((name, words, cwd, redir, [a for a in assigns if "/" in a or a.startswith("~")]))
        if name in CD:
            target = _args(words)[:1] or (["~"] if name == "cd" else [])
            cwd = _join(cwd, target[0]) if target and cwd else cwd
        elif depth < 3 and (name in SHELLS and "-c" in words or name == "eval"):
            code = words[words.index("-c") + 1:][:1] if name in SHELLS else [" ".join(words[1:])]
            for c in code:
                out += commands(c, cwd, depth + 1)
        elif depth < 3 and "--" in words and any(os.path.basename(w) == "mentat_serve.py" for w in words):
            out += commands(shlex.join(words[words.index("--") + 1:]), cwd, depth + 1)  # the wrapped command
    return out


def analyse(cmd, cwd=None):
    reads, writes = [], []
    for name, words, cwd_, redir, assigned in commands(cmd, cwd):
        reads += [_join(cwd_, a) for a in assigned]
        if name in CD:
            target = _args(words)[:1] or (["~"] if name == "cd" else [])
            reads += [_join(cwd_, t) for t in target]
            continue
        writes += [_join(cwd_, w) for w in redir + _writes(name, words)]
        reads += _reads(words, cwd_) + [_join(cwd_, w) for w in redir] + ([cwd_] if cwd_ and words else [])
    return reads, writes
