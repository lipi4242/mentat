"""Rule parsing and matching for szerep_guard.py.

The deny rules are OUR OWN subset of permission-rule syntax, matched with
fnmatch (not Claude Code's own matcher):
    Bash(<glob>)                 against the command and each normalised segment
                                 (whitespace collapsed, git global options dropped)
    GitPush(protected)           parsed rule: a git push is denied unless it names
                                 an explicit refspec whose destination is not
                                 HEAD/main/master, with no force/mirror/all flags
    Read(<glob>)                 Read, the path of Grep/Glob, and every path a Bash
                                 command reads (szerep_bash: cd, bare names, code)
    Edit(<glob>) / Write(<glob>) any of Edit, Write, MultiEdit, NotebookEdit, and the
                                 paths a Bash command writes (sed -i, >, tee, cp, …),
                                 except the tool refresh under .mentat/bin/ (not the guard)
    mcp__<glob> (or any glob)    against the tool name
Implicit forbidden-path denies come from szerep_tiltott.py. File paths are matched repo-relative, lexically normalised AND symlink-resolved;
either form matching denies. The guard prevents accidents; it is not a security
boundary.
"""
import fnmatch
import os
import pathlib
import posixpath
import re

from szerep_bash import analyse  # noqa: E402
from szerep_git import normalise as _normalise, push_violation  # noqa: E402


class GuardError(Exception):
    pass


RULE = re.compile(r"^(Bash|Read|Edit|Write|GitPush)\((.*)\)$")
WRITERS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READERS = {"Read", "Grep", "Glob"}
# Bash may refresh the vendored tools, except the code the guard itself runs or imports
# (bekotes/, manifest/); there only BEKOTES step 0's loop target is allowed.
TOOLS, GUARD_CODE = ".mentat/bin/*", (".mentat/bin/bekotes", ".mentat/bin/manifest")
REFRESH_LOOP = ".mentat/bin/bekotes/${f#*/}"
def parse_deny(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        raise GuardError("role file has no frontmatter")
    lines, deny, found = m.group(1).split("\n"), [], False
    for i, line in enumerate(lines):
        if not line.startswith("deny:"):
            continue
        found = True
        rest = line[5:].strip()
        if rest.startswith("["):
            items = re.findall(r"\"([^\"]*)\"|'([^']*)'|([^,\s\[\]][^,\]]*)", rest)
            deny = [a or b or c.strip() for a, b, c in items]
        else:
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s.startswith("- "):
                    break
                deny.append(s[2:].strip().strip("\"'"))
    if not found:
        raise GuardError("role file has no deny list")
    return deny


def builtin_rules(brain_root):
    """Denied for every role, so a role cannot widen itself."""
    brain = posixpath.normpath(brain_root or ".")
    rules = ["mentat.json", ".mentat/**", ".claude/settings*.json",
             ("" if brain == "." else brain + "/") + "szerepek/**"]
    return ["Edit(%s)" % r for r in rules]


def split_segments(cmd):
    return [s for s in re.split(r"&&|\|\||[;|&\n]", cmd) if s.strip()]


def segments(cmd):
    parts = split_segments(cmd)
    return [" ".join(cmd.split())] + [_normalise(s) for s in parts]


def _rel_forms(raw, root):
    forms = set()
    for base in {root, root.resolve()}:
        for cand in (pathlib.Path(os.path.normpath(raw)),
                     pathlib.Path(raw).resolve() if raw else None):
            if cand is None:
                continue
            if cand.is_absolute():
                try:
                    cand = cand.relative_to(base)
                except ValueError:
                    pass
            forms.update((cand.as_posix(), cand.as_posix() + "/"))
    return forms


def _path_of(tool, inp):
    key = {"NotebookEdit": "notebook_path", "Grep": "path", "Glob": "path"}.get(tool, "file_path")
    return inp.get(key) or inp.get("file_path") or inp.get("notebook_path") or inp.get("path")


def bash_paths(cmd, cwd=None):
    """Paths a Bash command reads (see szerep_bash.analyse)."""
    return analyse(cmd, cwd)[0]


def _any_form(paths, glob, root, fold):
    g = glob.lower() if fold else glob
    return any(fnmatch.fnmatchcase(f, g) or fnmatch.fnmatchcase("/" + f, g)
               for p in paths for f in (x.lower() if fold else x for x in _rel_forms(p, root)))


def _tool_refresh(path, root):
    forms = {f.lower().rstrip("/") for f in _rel_forms(path, root)}
    if REFRESH_LOOP.lower() in forms:
        return True
    guard = any(f == g or f.startswith(g + "/") for f in forms for g in GUARD_CODE)
    return not guard and any(f == TOOLS[:-2] or fnmatch.fnmatchcase(f, TOOLS) for f in forms)


def match(rule, tool, inp, root, fold=False, cwd=None):
    m = RULE.match(rule)
    if not m:
        return fnmatch.fnmatchcase(tool, rule)
    kind, glob = m.groups()
    if kind == "GitPush":
        cmd = str(inp.get("command", ""))
        return tool == "Bash" and any(push_violation(s) for s in split_segments(cmd))
    if kind == "Bash":
        return tool == "Bash" and any(fnmatch.fnmatchcase(s, glob)
                                      for s in segments(str(inp.get("command", ""))))
    if tool == "Bash" and kind in ("Read", "Edit", "Write"):
        reads, writes = analyse(str(inp.get("command", "")), cwd)
        if kind != "Read":  # the documented tool refresh (BEKOTES step 0, skills) writes here
            writes = [w for w in writes if not _tool_refresh(w, root)]
        return _any_form(reads if kind == "Read" else writes, glob, root, fold)
    ok = tool in (WRITERS if kind in ("Edit", "Write") else READERS)
    raw = _path_of(tool, inp)
    if not ok or not raw:
        return False
    if fold:
        glob = glob.lower()
    return any(fnmatch.fnmatchcase(f, glob) or fnmatch.fnmatchcase("/" + f, glob)
               for f in (x.lower() if fold else x for x in _rel_forms(str(raw), root)))
