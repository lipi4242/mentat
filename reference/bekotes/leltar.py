"""Deterministic, LLM-free inventory of the sources listed in bekotes.json."""
import hashlib
import pathlib
import re
import os
import subprocess

import fajlszuro as fs
import szuro

OK = "elérhető"
RESTRICT = ("tiltott", "nem alkalmazható")
MAX_SIZE = 256 * 1024
CONFIGS = {"package.json", "wrangler.toml", "pyproject.toml", ".release-agent/config.json"}


def resolve(root, rel):
    """Repo-relative or ~/ path; '..' and other absolute paths are rejected."""
    if ".." in pathlib.PurePath(rel).parts:
        raise ValueError("'..' tilos az útvonalban: %s" % rel)
    if rel.startswith("~/"):
        return pathlib.Path(rel).expanduser()
    if pathlib.PurePath(rel).is_absolute():
        raise ValueError("abszolút útvonal tilos: %s" % rel)
    return pathlib.Path(root) / rel


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# Never fetch a missing blob on demand: in a partial clone that would bring the forbidden files in.
NO_LAZY = dict(os.environ, GIT_NO_LAZY_FETCH="1")


def _git(p, *args):
    r = subprocess.run(["git", "-C", str(p), *args], capture_output=True, text=True, env=NO_LAZY)
    return r.stdout if r.returncode == 0 else None


def _size(p, path):
    """Size of a tracked file without touching a remote: the work tree, else the local object."""
    f = pathlib.Path(p) / path
    if f.is_file() and not f.is_symlink():
        return f.stat().st_size
    out = _git(p, "cat-file", "-s", "HEAD:" + path)
    return int(out) if out and out.strip().isdigit() else 0


def _repo(p, globs=()):
    if _git(p, "rev-parse", "--git-dir") is None or _git(p, "rev-parse", "HEAD") is None:
        return None
    files, docs, configs = [], [], []
    for path in (_git(p, "ls-tree", "-r", "--name-only", "-z", "HEAD") or "").split("\0"):
        if not path:
            continue
        if fs.tiltott(path, globs):  # never read: name only
            files.append({"path": path, "tiltott": True})
            continue
        if fs.excluded(path):
            continue
        size = _size(p, path)
        f = {"path": path, "size": size}
        if size > MAX_SIZE:
            f["skipped"] = "meret"
        files.append(f)
        if fs.is_doc(path):
            docs.append(path)
        if path in CONFIGS:
            configs.append(path)
    commits = []
    for line in (_git(p, "log", "-50", "--format=%H%x1f%cI%x1f%s") or "").splitlines():
        sha, date, subject = line.split("\x1f", 2)
        commits.append({"sha": sha, "date": date, "subject": szuro.redact(subject)[0]})
    return {
        "head": _git(p, "rev-parse", "HEAD").strip(),
        "branch": szuro.redact((_git(p, "rev-parse", "--abbrev-ref", "HEAD") or "").strip())[0],
        "release_agent": (pathlib.Path(p) / ".release-agent").exists(),
        "dirty": bool((_git(p, "status", "--porcelain") or "").strip()),
        "commits": commits, "files": sorted(files, key=lambda f: f["path"]),
        "docs": sorted(docs), "configs": sorted(configs)}


def _memory(p, globs=()):
    out = []
    for f in sorted(pathlib.Path(p).glob("*.md")):
        if fs.tiltott(f.name, globs):  # never read or hashed: name only
            out.append({"file": szuro.redact(f.name)[0], "tiltott": True})
            continue
        if f.is_symlink():  # could alias a forbidden or outside file: never followed
            out.append({"file": szuro.redact(f.name)[0], "symlink": True})
            continue
        text = f.read_text(encoding="utf-8")
        e = {"file": szuro.redact(f.name)[0], "sha256": _sha(f)}
        m = re.search(r"^description:\s*(.+)$", text, re.M)
        if szuro.suspicious(text):
            e["flagged"] = "gyanus-utasitas"
        else:
            e["description"] = szuro.redact(m.group(1).strip())[0] if m else "-"
        out.append(e)
    return {"files": out}


def _linear(p, globs=()):
    import json
    d = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    issues = [{"id": i.get("id"), "identifier": i.get("identifier"),
               "title": szuro.redact(i.get("title") or "")[0],
               "state": szuro.redact(str(i.get("state") or ""))[0], "updatedAt": i.get("updatedAt")}
              for i in d.get("issues", [])]
    issues.sort(key=lambda i: str(i["identifier"]))
    return {"exported_at": d.get("exported_at"), "complete": bool(d.get("complete")),
            "max_updated_at": max((str(i["updatedAt"]) for i in issues if i["updatedAt"]), default=None),
            "issues": issues}


def _live(p, globs=()):
    raw = pathlib.Path(p).read_bytes()
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": len(raw.splitlines())}


def _one(src, root):
    name, kind = src["name"], src["kind"]
    base = {"name": name, "kind": kind}
    st = src.get("state")
    if st in RESTRICT or (kind == "mail" and not st):
        return {**base, "state": st or "tiltott", "reason": src.get("reason", "")}
    collectors = {"repo": _repo, "memory": _memory, "linear": _linear, "live": _live}
    if kind not in collectors:
        return {**base, "state": "blokkolt", "reason": "ismeretlen kind"}
    field = "export" if kind == "linear" else "path"
    rel = src.get(field)
    if not rel:  # súrlódás #21: ember-olvasható ok, nem nyers kivételnév
        hint = {"live": " (élő forrás: egy helyi fájl, pl. egy összesítő lekérdezés kimenete)",
                "linear": " (a linear_export.py kimenete)"}.get(kind, "")
        return {**base, "state": "blokkolt", "reason": "nincs megadva a %s mező%s" % (field, hint)}
    try:
        p = resolve(root, rel)
        ok = p.is_dir() if kind in ("repo", "memory") else p.is_file()
        data = collectors[kind](p, fs.globs_of(src)) if ok else None
    except (OSError, ValueError, KeyError, UnicodeError) as e:
        return {**base, "state": "blokkolt", "reason": "nem olvasható: %s" % type(e).__name__}
    if data is None:
        return {**base, "state": "blokkolt", "reason": "hiányzó vagy nem olvasható: %s" % rel}
    if kind == "live":
        data["path"] = rel
    return {**base, "state": OK, **data}


def collect(cfg, repo_root):
    sources = sorted((_one(s, repo_root) for s in cfg["sources"]), key=lambda s: s["name"])
    gaps = [{"name": s["name"], "state": s["state"],
             "reason": s.get("reason") or "hiányos export"}
            for s in sources if s["state"] != OK or s.get("complete") is False]
    return {"schema": 1, "business": cfg.get("business"), "sources": sources,
            "hianylista": gaps,
            "kiado_alapnak": not any(s.get("release_agent") for s in sources)}
