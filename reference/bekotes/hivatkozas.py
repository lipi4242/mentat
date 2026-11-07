"""Citations in the knowledge map: `(forrás: <source-name>:<path or id>)`.

A repo citation must name an existing file (on disk or in the inventory), a
memory citation a file of the approved extract (<biz>/memoria/), a linear
citation an issue identifier of the export, a live citation its file name; mail needs only the name.
A source some installed role may not Read is never cited in the shared map files
(korlatozott.py): its facts go under <biz>/<folder>/, behind the same deny.
"""
import pathlib
import re

import fajlszuro as fs
import hely
import korlatozott
import leltar as lt

CITE = re.compile(r"\(forrás: ([^()]+)\)")
ONE = re.compile(r"^([^:()\s,;]+):(.+)$")
MAP_FILES = ("terkep", "business", "rendszerek", "emberek")


def citations(text):
    """Every `name:ref` inside `(forrás: …)`; several may share one parenthesis (`,` or `;`),
    and a part without `name:` (a date, a note) is not a citation."""
    out = []
    for inner in CITE.findall(text):
        for part in re.split(r"[,;]", inner):
            m = ONE.match(part.strip())
            if m:
                out.append((m.group(1), m.group(2).strip()))
    return out


def _on_disk(repo, rel, ref):
    try:
        return (lt.resolve(repo, rel) / ref).exists() if rel else False
    except ValueError:
        return False


def _ok(src, ref, repo, biz, inv):
    kind = src.get("kind")
    ref = ref.split("#", 1)[0].strip()
    if kind in ("repo", "memory"):
        if not ref or ref.startswith(("/", "~")) or ".." in pathlib.PurePosixPath(ref).parts:
            return False
        try:
            if fs.tiltott(ref, fs.globs_of(src)):
                return False  # a forbidden path is never a citable source
        except ValueError:
            return False
        if kind == "memory":  # only the approved extract counts, never the raw source
            return (biz / "memoria" / ref).is_file()
        listed = {f.get("path") or f.get("file") for f in inv.get("files") or []
                  if isinstance(f, dict) and not f.get("tiltott")} | set(inv.get("docs") or [])
        return ref in listed or _on_disk(repo, src.get("path"), ref)
    if kind == "linear":
        ids = {i.get("identifier") for i in inv.get("issues") or [] if isinstance(i, dict)}
        try:
            export = hely.read_json(lt.resolve(repo, src.get("export") or "")) or {}
        except ValueError:
            export = {}
        ids |= {i.get("identifier") for i in export.get("issues") or [] if isinstance(i, dict)}
        return ref in ids
    if kind == "live":  # the file name (or the configured path) of the live source
        path = str(src.get("path") or "")
        return ref in (path, pathlib.PurePosixPath(path).name)
    return True


def check(repo, biz, cfg, lel):
    """(number of citations, list of bad 'source:ref' strings)."""
    sources = {s.get("name"): s for s in (cfg or {}).get("sources") or [] if isinstance(s, dict)}
    inv = {s.get("name"): s for s in (lel or {}).get("sources") or [] if isinstance(s, dict)}
    total, bad = 0, []
    closed = korlatozott.restricted(repo, cfg)
    for n in MAP_FILES:
        p = biz / (n + ".md")
        if not p.is_file():
            continue
        for name, ref in citations(p.read_text(encoding="utf-8", errors="replace")):
            total += 1
            src = sources.get(name)
            if name in closed:
                bad.append("%s:%s (korlátozott forrás a közös térképen: a tény helye %s/)"
                           % (name, ref, closed[name]))
            elif src is None or not _ok(src, ref, pathlib.Path(repo), biz, inv.get(name) or {}):
                bad.append("%s:%s" % (name, ref))
    return total, bad
