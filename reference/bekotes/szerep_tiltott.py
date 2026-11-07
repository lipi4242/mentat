"""Forbidden-path rules for szerep_guard.py, from every <root>/business/*/bekotes.json.

- every role: Read(<src>/<glob>) and Read(<src>/*/<glob>) per tiltott glob (a leading
  `**/` also matches at the source root, like fajlszuro.tiltott);
- every role except DEV_ROLE: the same for SECRET_GLOBS in every repo/memory source,
  and Grep/Glob whose path (without one: the cwd) is a forbidden location's directory
  or an ancestor of it. The developer works with the full repo; `$BK olvas` stays the rule.
A malformed config is skipped so the agent is never locked out of fixing it.
"""
import json
import os
import pathlib
import posixpath

from fajlszuro import SECRET_GLOBS

DEV_ROLE = "fejleszto"
WILD = set("*?[")


def sources(root, brain_root):
    """[(kind, base path, globs)] for every source with a usable path."""
    brain = posixpath.normpath(brain_root or ".")
    out = []
    for cfg_path in sorted((pathlib.Path(root) / brain / "business").glob("*/bekotes.json")):
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in (cfg.get("sources") if isinstance(cfg, dict) else None) or []:
            if not isinstance(s, dict):
                continue
            path = s.get("export" if s.get("kind") == "linear" else "path")
            globs = s.get("tiltott") if isinstance(s.get("tiltott"), list) else []
            if not isinstance(path, str) or not path or ".." in path.split("/"):
                continue
            base = os.path.expanduser(path) if path.startswith("~/") else posixpath.normpath(path)
            out.append((s.get("kind"), base.rstrip("/"), [g for g in globs if isinstance(g, str) and g]))
    return out


def _variants(base, g):
    out = ["%s/%s" % (base, g), "%s/*/%s" % (base, g)]
    return out + (["%s/%s" % (base, g[3:])] if g.startswith("**/") else [])


def read_rules(root, brain_root, role):
    out = []
    for kind, base, globs in sources(root, brain_root):
        extra = SECRET_GLOBS if role != DEV_ROLE and kind in ("repo", "memory") else []
        for g in globs + extra:
            out += ["Read(%s)" % v for v in _variants(base, g)]
    return out


def _forms(p):
    return {os.path.normpath(str(p)).lower(), os.path.realpath(str(p)).lower()}


def _locations(root, brain_root):
    for _kind, base, globs in sources(root, brain_root):
        for g in globs:
            lit = []
            for part in g.split("/")[:-1]:
                if WILD & set(part):
                    break
                lit.append(part)
            b = pathlib.Path(base)
            yield (b if b.is_absolute() else pathlib.Path(root) / b).joinpath(*lit)


def grep_denied(root, brain_root, role, tool, inp, cwd):
    """The forbidden location a Grep/Glob would sweep, or None."""
    if role == DEV_ROLE or tool not in ("Grep", "Glob"):
        return None
    raw = pathlib.Path(str(inp.get("path") or cwd or root))
    target = _forms(raw if raw.is_absolute() else pathlib.Path(root) / raw)
    for loc in _locations(root, brain_root):
        for lf in _forms(loc):
            if any(lf == t or lf.startswith(t.rstrip("/") + "/") for t in target):
                return str(loc)
    return None


def role_swept(root, brain_root, deny, tool, inp, cwd, match):
    """A source the role may not read (one of its Read rules matches the source path) that a
    Grep/Glob would sweep (its path, or the cwd, is the source or an ancestor), for every role."""
    if tool not in ("Grep", "Glob") or not deny:
        return None
    raw = pathlib.Path(str(inp.get("path") or cwd or root))
    target = _forms(raw if raw.is_absolute() else pathlib.Path(root) / raw)
    for _kind, base, _globs in sources(root, brain_root):
        b = pathlib.Path(base)
        b = b if b.is_absolute() else pathlib.Path(root) / b
        if not any(match(r, "Read", {"file_path": str(b)}, root, fold=True) for r in deny):
            continue
        for lf in _forms(b):
            if any(lf == t or lf.startswith(t.rstrip("/") + "/") for t in target):
                return str(b)
    return None
