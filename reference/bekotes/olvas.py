"""`olvas grep|show`: targeted reads over the business sources, never a forbidden path.

Sources come from <root>/business/<name>/bekotes.json: repo -> its clone, memory ->
the approved extract (<biz>/memoria/), live and linear -> their file; sources with
a state (tiltott, nem alkalmazható, blokkolt) and mail are skipped. Forbidden globs
and excluded paths (node_modules, .git, binaries, ...) are skipped by grep and
refused by show. Symlinks are never followed.
"""
import os
import pathlib
import re
import subprocess
import sys

import fajlszuro as fs
import hely
import leltar as lt
import olvas_szerep
import szuro

MAX_SIZE = 1024 * 1024
MAX_HITS = 200


def _business(repo, name):
    if name:
        return name
    found = sorted(p.parent.name for p in (repo / hely.brain_root(repo) / "business").glob("*/bekotes.json"))
    if len(found) != 1:
        raise hely.HelyError("add meg a --business-t (talált: %s)" % (", ".join(found) or "egy sem"))
    return found[0]


def _sources(repo, business):
    biz = hely.biz_dir(repo, business)
    cfg = hely.read_json(biz / "bekotes.json")
    if cfg is None:
        raise hely.HelyError("nincs bekotes.json: %s" % biz)
    out = {}
    for s in cfg.get("sources") or []:
        if not isinstance(s, dict) or s.get("state") or s.get("kind") == "mail":
            continue
        kind = s.get("kind")
        rel = s.get("export") if kind == "linear" else s.get("path")
        base = biz / "memoria" if kind == "memory" else (lt.resolve(repo, rel) if rel else None)
        if base is not None:
            out[s.get("name")] = (base, fs.globs_of(s) + fs.SECRET_GLOBS,
                                  _tracked(base) if kind == "repo" else None)
    return out


def _tracked(base):
    """Files git tracks in a repo source; untracked files (a local .env) are never read."""
    try:
        r = subprocess.run(["git", "-C", str(base), "ls-files", "-z"], capture_output=True, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    except OSError:
        return set()
    return set(r.stdout.decode("utf-8", "replace").split("\0")) - {""} if r.returncode == 0 else set()


def _readable(base, rel, globs, tracked):
    p = base / rel
    lexical = base.resolve().joinpath(*rel.split("/"))
    return not (fs.excluded(rel) or fs.tiltott(rel, globs) or (tracked is not None and rel not in tracked)
                or p.is_symlink() or lexical.resolve() != lexical or not p.is_file())


def _walk(base, globs, tracked):
    if base.is_file() and not base.is_symlink():
        if not fs.tiltott(base.name, globs):
            yield base.name, base
        return
    if tracked is not None:
        names = sorted(tracked)
    else:
        names = []
        for d, dirs, files in os.walk(base):  # never follows symlinked dirs
            dirs[:] = sorted(x for x in dirs if x not in fs.EXCLUDE_DIRS)
            names += [(pathlib.Path(d) / f).relative_to(base).as_posix() for f in sorted(files)]
    for rel in names:
        if _readable(base, rel, globs, tracked):
            yield rel, base / rel


def grep(a, srcs):
    try:
        rx = re.compile(a.pattern)
    except re.error as e:
        raise hely.HelyError("hibás minta: %s" % e)
    hits, skipped = [], set()
    for name, (base, globs, tracked) in sorted(srcs.items()):
        if a.source and name != a.source:
            continue
        for rel, p in _walk(base, globs, tracked):
            if olvas_szerep.denied(a.repo_path, a.deny, p):
                skipped.add(name)
                continue
            try:
                if p.stat().st_size > MAX_SIZE:
                    continue
                lines = p.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            hits += ["%s:%s:%d: %s" % (name, rel, i, szuro.redact(ln[:300])[0])
                     for i, ln in enumerate(lines, 1) if rx.search(ln)]
    if skipped:
        print("a(z) %s szerep nem olvashatja, kihagyva: %s" % (a.role, ", ".join(sorted(skipped))), file=sys.stderr)
        if a.source in skipped and not hits:
            return 1
    print("\n".join(hits[:MAX_HITS]) + ("\n… (+%d további találat)" % (len(hits) - MAX_HITS)
                                         if len(hits) > MAX_HITS else ""))
    return 0


def show(a, srcs):
    name, _, rel = a.ref.partition(":")
    if name not in srcs:
        raise hely.HelyError("ismeretlen vagy nem olvasható forrás: %s" % name)
    base, globs, tracked = srcs[name]
    if base.is_file():
        rel = rel or base.name
    parts = rel.replace("\\", "/").split("/")
    if rel.startswith(("/", "~")) or any(x in ("", ".", "..") for x in parts):
        raise hely.HelyError("érvénytelen útvonal (üres, '.', '..' vagy abszolút rész): %s" % a.ref)
    root = base.parent if base.is_file() else base
    lexical = root.resolve().joinpath(*parts)
    target = lexical.resolve()
    if base.is_file() and target != base.resolve():
        raise hely.HelyError("ennek a forrásnak egyetlen fájlja van: %s" % base.name)
    try:
        real = target.relative_to(root.resolve()).as_posix()
    except ValueError:
        real = None
    if fs.tiltott(rel, globs) or (real and fs.tiltott(real, globs)):
        print("tiltott útvonal (bekotes.json tiltott vagy titok-minta): %s — nem nyitom meg" % a.ref,
              file=sys.stderr)
        return 1
    if real is None or target != lexical or fs.excluded(real) or not target.is_file() \
            or (tracked is not None and real not in tracked):
        print("nem olvasható (követetlen, kizárt, symlink, a forráson kívül vagy hiányzik): %s" % a.ref,
              file=sys.stderr)
        return 1
    rule = olvas_szerep.denied(a.repo_path, a.deny, target)
    if rule:
        print("a(z) %s szerep ezt nem olvashatja (%s): %s" % (a.role, rule, a.ref), file=sys.stderr)
        return 1
    try:
        sys.stdout.write(szuro.redact(target.read_text(encoding="utf-8"))[0])  # a named source is still filtered
    except UnicodeDecodeError:
        print("nem szöveges fájl: %s" % a.ref, file=sys.stderr)
        return 1
    return 0


def run(a):
    repo = pathlib.Path(a.repo)
    a.repo_path = repo.resolve()
    a.role, a.deny = olvas_szerep.rules(a.repo_path)
    srcs = _sources(repo, _business(repo, a.business))
    return grep(a, srcs) if a.osub == "grep" else show(a, srcs)
