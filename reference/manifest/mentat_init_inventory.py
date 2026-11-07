"""What mentat_init.py found in the folder, what it committed, what it left alone (machine facts).

scan(root) runs BEFORE anything is written: file kinds, half-finished app signs (a project
manifest, TODO/FIXME lines in code), notes and todo files, other agents' instruction files.
found_lines / after_lines turn it into a few lines in the USER's language for the agent to pass
on. Uncommitted changes are listed file by file from `git status` AFTER the brain's commit,
which takes only the tool's own files: the USER's changes stay as they are until they decide.
"""
import os
import pathlib
import re
import subprocess

import mentat_secret_scan as secret_scan  # noqa: E402

SKIP = {".git", ".mentat", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".claude"}
KINDS = {"note": {".md", ".txt", ".doc", ".docx", ".odt", ".rtf", ".pdf"},
         "table": {".csv", ".tsv", ".xls", ".xlsx", ".ods", ".numbers"},
         "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sh", ".php", ".rb", ".go", ".sql"},
         "image": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".heic", ".webp"}}
APP = ("package.json", "requirements.txt", "pyproject.toml", "wrangler.toml", "Cargo.toml", "go.mod",
       "composer.json", "Gemfile", "Dockerfile")
FOREIGN = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules", "copilot-instructions.md")
TODO = re.compile(r"\b(TODO|FIXME|XXX)\b")
TODO_NAME = re.compile(r"(todo|teendo|teendő|tasks|feladat|notes|jegyzet)", re.I)
MAX_FILES = 5000
T = {"hu": {"empty": "A mappa üres volt: nincs mit átvenni.",
            "found": "Ezt találtam a mappában: %s.", "kinds": {"note": "%d jegyzet/dokumentum", "table": "%d táblázat",
            "code": "%d kódfájl", "image": "%d kép", "other": "%d egyéb"}, "app": "Félkész app jelei: %s.",
            "todo": "%d TODO/FIXME a kódban", "named": "Jegyzet- és teendőfájlok: %s.",
            "foreign": "Más ágens utasításfájlja (adat, nem követem; előbb kérdezek): %s.",
            "left": "Nem commitolt változások (nem nyúltam hozzájuk, a döntésedig így maradnak): %s.",
            "committed": "A commitba ez került: %s.", "nothing": "A commitba most nem került semmi új."},
     "en": {"empty": "The folder was empty: nothing to take over.",
            "found": "Found in this folder: %s.", "kinds": {"note": "%d notes/documents", "table": "%d tables",
            "code": "%d code files", "image": "%d images", "other": "%d other"}, "app": "Signs of a half-finished app: %s.",
            "todo": "%d TODO/FIXME in the code", "named": "Note and todo files: %s.",
            "foreign": "Another agent's instruction file (data, not followed; I ask first): %s.",
            "left": "Uncommitted changes (I did not touch them; they stay until you decide): %s.",
            "committed": "Committed: %s.", "nothing": "Nothing new was committed."}}


def _short(items, n=6):
    return ", ".join(items[:n]) + (" … (+%d)" % (len(items) - n) if len(items) > n else "")


def _files(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP)
        for n in sorted(names):
            yield pathlib.Path(d) / n


def scan(root):
    root, inv = pathlib.Path(root), {"kinds": {}, "app": [], "todo": 0, "named": [], "foreign": []}
    inv["tell"] = secret_scan.lines(root)  # a takeover: a key already in the history is said first
    for seen, p in enumerate(_files(root)):
        if seen >= MAX_FILES:
            break
        rel, name, ext = p.relative_to(root).as_posix(), p.name, p.suffix.lower()
        if name in FOREIGN:
            inv["foreign"].append(rel)
            continue
        kind = next((k for k, exts in KINDS.items() if ext in exts), "other")
        inv["kinds"][kind] = inv["kinds"].get(kind, 0) + 1
        if name in APP:
            inv["app"].append(rel)
        if kind in ("note", "table") and TODO_NAME.search(name):
            inv["named"].append(rel)
        if kind == "code" and p.stat().st_size < 1_000_000:
            inv["todo"] += len(TODO.findall(p.read_text(encoding="utf-8", errors="replace")))
    return inv


def found_lines(inv, lang):
    t = T[lang]
    if not inv["kinds"] and not inv["foreign"]:
        return [t["empty"]] + inv.get("tell", [])
    kinds = [t["kinds"][k] % n for k, n in sorted(inv["kinds"].items(), key=lambda kv: -kv[1])]
    out = [t["found"] % ", ".join(kinds)] if kinds else []
    signs = inv["app"] + ([t["todo"] % inv["todo"]] if inv["todo"] else [])
    if signs:
        out.append(t["app"] % _short(signs))
    if inv["named"]:
        out.append(t["named"] % _short(inv["named"]))
    if inv["foreign"]:
        out.append(t["foreign"] % _short(inv["foreign"]))
    return out + inv.get("tell", [])


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)


def after_lines(root, before_head, lang):
    """The files of the brain's commit (if one was made now) and what is still uncommitted."""
    t, out = T[lang], []
    head = _git(root, "rev-parse", "-q", "--verify", "HEAD").stdout.strip()
    if head and head != before_head:
        files = _git(root, "show", "--name-only", "--format=", "--relative", "HEAD").stdout.split()
        out.append(t["committed"] % ("%s (%d)" % (_short(files), len(files))))
    else:
        out.append(t["nothing"])
    left = [ln[:2].strip() + " " + ln[3:] for ln in _git(root, "status", "--porcelain", "--", ".").stdout.splitlines()]
    if left:
        out.append(t["left"] % _short(left, 8))
    return out


def head(root):
    return _git(root, "rev-parse", "-q", "--verify", "HEAD").stdout.strip()
