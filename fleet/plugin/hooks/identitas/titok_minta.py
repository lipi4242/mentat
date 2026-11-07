"""Mi titok a titok-kapu (titok_kapu.py) szemével. Csak nevet és stat-ot néz, tartalmat SOHA.

    Leltar.load()                  ~/.mentat/titkok/leltar.json (a `fleet secrets scan` írja)
    secret(path, cwd, lel, rec)    ok-szöveg vagy None: leltár (realpath vagy dev+inode), átirat,
                                   fájlnév-heurisztika, /proc/*/environ, glob, rekurzív mappa

A leltár nélkül is él: az átirat-, környezet- és fájlnév-szabály mindig érvényes.
"""
import fnmatch
import glob
import json
import os
import re

STRONG = re.compile(r"^(\.env(\..*)?|.*\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_(rsa|dsa|ecdsa|ed25519)(\..*)?|"
                    r".*service[-_]?account.*\.json|\.?credentials(\..*)?)$", re.I)
WORD = re.compile(r"(^|[._-])(api[_-]?)?keys?([._-]|$)|token|secret|credential|passw|private[_-]?key", re.I)
EXEMPT = (".example", ".sample", ".template", ".tmpl", ".dist", ".pub")
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".md", ".rst", ".sh", ".go", ".rs", ".rb",
            ".java", ".kt", ".c", ".h", ".cpp", ".html", ".css", ".txt", ".lock"}
GLOB = re.compile(r"[*?\[]")
WALK_BUDGET = 20000


def home():
    return os.path.realpath(os.path.expanduser("~"))


def leltar_path():
    return os.path.join(home(), ".mentat", "titkok", "leltar.json")


def name_hit(base):
    if not base or base.endswith(EXEMPT):
        return False
    if STRONG.match(base):
        return True
    return os.path.splitext(base)[1].lower() not in CODE_EXT and bool(WORD.search(base))


class Leltar:
    def __init__(self, files=()):
        self.paths = {f["path"] for f in files if f.get("path")}
        self.ids = {(f["dev"], f["ino"]) for f in files if f.get("dev") is not None and f.get("ino") is not None}

    @classmethod
    def load(cls, path=None):
        try:
            with open(path or leltar_path(), encoding="utf-8") as fh:
                data = json.load(fh)
            return cls([f for f in data.get("files", []) if isinstance(f, dict) and f.get("class") != "atirat"])
        except (OSError, ValueError, AttributeError, TypeError):
            return cls()

    def has(self, p):
        if p in self.paths:
            return True
        try:
            st = os.stat(p)
        except OSError:
            return False
        return (st.st_dev, st.st_ino) in self.ids

    def under(self, d):
        d = d.rstrip(os.sep) + os.sep
        return any(x.startswith(d) for x in self.paths)


def claude_roots():
    roots = glob.glob(os.path.join(home(), ".claude*"))
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        roots.append(os.environ["CLAUDE_CONFIG_DIR"])
    return [os.path.realpath(r) for r in roots if os.path.isdir(r)]


def in_transcripts(p):
    """Egy ~/.claude*/projects/ alatt (a memory/ mappák kivételével: azok az ágens saját jegyzetei)."""
    for r in claude_roots():
        proj = os.path.join(r, "projects")
        if p == proj or p.startswith(proj + os.sep):
            return "memory" not in p[len(proj):].split(os.sep)
    return False


def holds_transcripts(d):
    d = d.rstrip(os.sep) + os.sep
    return any(os.path.join(r, "projects").startswith(d) for r in claude_roots())


def secret_root(p):
    """A titkok szokásos lakhelye: ~/.config/<x>/, ~/.claude*/, ~/.mentat/, ~/.ssh/."""
    h = home() + os.sep
    if not p.startswith(h):
        return False
    rel = p[len(h):].split(os.sep)
    return (rel[0] == ".config" and len(rel) > 2) or rel[0].startswith(".claude") or rel[0] in (".mentat", ".ssh")


def lel_under_root(lel, d):
    """Van-e a `d` alatt olyan leltár-fájl, ami titok-mappában él (egy repó saját .env-je nem ilyen:
    a Grep eszköz a .gitignore-t és a rejtett fájlokat amúgy is kihagyja)."""
    d = d.rstrip(os.sep) + os.sep
    return any(x.startswith(d) and secret_root(os.path.dirname(x)) for x in lel.paths)


def _file(p, lel, rec):
    if lel.has(p):
        return "leltárban"
    if in_transcripts(p) and (p.endswith(".jsonl") or os.path.isdir(p)):
        return "átirat"
    if re.match(r"^/proc/[^/]+/environ$", p):
        return "környezet"
    if os.path.isdir(p):
        return _tree(p, lel) if rec else None
    return "kulcsfájl-név" if name_hit(os.path.basename(p)) else None


def _tree(d, lel):
    if lel.under(d):
        return "leltárban (mappa)"
    if holds_transcripts(d) or in_transcripts(d):
        return "átiratokat tartalmazó mappa"
    n = 0
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "__pycache__", ".venv")]
        n += len(files) + len(dirs)
        if n > WALK_BUDGET:
            return "túl nagy mappa, nem ellenőrizhető"
        if any(name_hit(f) for f in files) or (in_transcripts(root) and any(f.endswith(".jsonl") for f in files)):
            return "kulcsfájl a mappában"
    return None


def resolve(path, cwd):
    p = path.replace("${HOME}", "~").replace("$HOME", "~")
    if "$" in p or "`" in p:
        return None
    return os.path.realpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(p)))


def secret(path, cwd, lel, rec=False):
    p = resolve(path, cwd)
    if p is None:
        return None
    if not GLOB.search(p):
        return _file(p, lel, rec)
    hits = glob.glob(p)[:500]
    for h in hits:
        why = _file(os.path.realpath(h), lel, rec)
        if why:
            return why
    if any(fnmatch.fnmatch(x, p) for x in lel.paths):
        return "leltárban (glob)"
    if not hits and (secret_root(os.path.dirname(p)) or in_transcripts(os.path.dirname(p))):
        return "titok-mappa (glob)"
    return "kulcsfájl-név" if not hits and name_hit(os.path.basename(p)) else None
