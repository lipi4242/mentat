"""Parsed git command handling for szerep_rules.py (shlex based, no globs)."""
import os
import re
import shlex

_ENVWORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = {"env", "command", "sudo", "nohup", "time", "exec"}
_GLOBAL_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--attr-source"}
_PUSH_ARG = {"--repo", "-o", "--push-option", "--receive-pack", "--exec", "--signed"}
_PROTECTED = {"head", "main", "master", "@"}


def _git_argv(seg):
    """(subcommand, rest) if seg is a git command; None if not; ("?", []) if unparseable."""
    try:
        toks = shlex.split(seg)
    except ValueError:
        return "?", []
    i = 0
    while i < len(toks) and (_ENVWORD.match(toks[i]) or toks[i] in _WRAPPERS or
                             (i and toks[i - 1] == "env" and toks[i].startswith("-"))):
        i += 1
    if i >= len(toks) or os.path.basename(toks[i]) != "git":
        return None
    i += 1
    while i < len(toks) and toks[i].startswith("-"):
        i += 2 if toks[i] in _GLOBAL_ARG else 1
    if i >= len(toks):
        return None
    return toks[i], toks[i + 1:]


def normalise(seg):
    g = _git_argv(seg)
    if g is None or g[0] == "?":
        return " ".join(seg.split())
    return " ".join(["git", g[0]] + g[1])


def push_violation(seg):
    """True if seg is a git push that is not provably a push to a non-protected branch."""
    g = _git_argv(seg)
    if g is None or (g[0] != "push" and g[0] != "?"):
        return False
    if g[0] == "?":
        return bool(re.search(r"\bpush\b", seg))
    pos, args, skip = [], g[1], False
    for a in args:
        if skip:
            skip = False
        elif a in _PUSH_ARG:
            skip = True
        elif a.startswith("--"):
            if a.startswith(("--force", "--mirror", "--all")):
                return True
        elif a.startswith("-") and len(a) > 1:
            if "f" in a[1:]:
                return True
        else:
            pos.append(a)
    if len(pos) < 2:
        return True
    for ref in pos[1:]:
        if ref.startswith("+"):
            return True
        dest = ref.rsplit(":", 1)[-1]
        dest = dest[len("refs/heads/"):] if dest.startswith("refs/heads/") else dest
        if not dest or "*" in dest or dest.lower() in _PROTECTED:
            return True
    return False
