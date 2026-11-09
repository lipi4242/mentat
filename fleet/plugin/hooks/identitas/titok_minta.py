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
            ".java", ".kt", ".c", ".h", ".cpp", ".html", ".css", ".txt", ".lock", ".sql"}
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


def _slug(d):
    """A Claude Code projekt-mappaneve: minden nem alfanumerikus jel „-" (/home/a/b → -home-a-b)."""
    return re.sub(r"[^A-Za-z0-9]", "-", d)


def _project_dirs(cwd):
    """A hívás cwd-je (nyersen és realpath-tal) és a git-gyökere: ezekből lesz a saját projekt neve."""
    out = set()
    for c in {cwd, os.path.realpath(cwd)}:
        out.add(c)
        d = c
        while not os.path.exists(os.path.join(d, ".git")) and os.path.dirname(d) != d:
            d = os.path.dirname(d)
        if os.path.exists(os.path.join(d, ".git")):
            out.add(d)
    return out


def _registered_workdir():
    """A FLEET_AGENT registryben rögzített workdir-je (%h = HOME), vagy None."""
    agent = os.environ.get("FLEET_AGENT", "").strip()
    raw = os.environ.get("FLEET_REGISTRY", "").strip()
    try:
        if agent and not raw:
            with open(os.path.join(home(), ".config", "fleet", "registry")) as fh:
                raw = fh.read().strip()
        if not agent or not raw:
            return None
        with open(os.path.join(os.path.expanduser(raw), "agents.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    rows = data.get("agents", []) if isinstance(data, dict) else data
    wd = next((r.get("workdir") for r in rows if isinstance(r, dict) and r.get("agent") == agent), None)
    return os.path.expanduser(wd.replace("%h", home())) if isinstance(wd, str) and wd else None


def session_dir(cwd):
    """A session RÖGZÍTETT projektje: CLAUDE_PROJECT_DIR (a Claude Code a hooknak adja), különben a
    FLEET_AGENT registry-workdirje, csak végső esetben a cwd — a `cd` ne tegye sajáttá más projektjét."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or _registered_workdir() or cwd


def _mem_match(p, dirs):
    mems = {os.path.join(r, "projects", _slug(d), "memory") for r in claude_roots() for d in dirs}
    if p in mems:
        return True
    if os.path.dirname(p) not in mems or not p.endswith(".md"):
        return False
    try:
        st = os.lstat(p)
    except OSError:
        return True  # még nem létezik: új jegyzet
    return os.path.isfile(p) and not os.path.islink(p) and st.st_nlink == 1


def own_memory(p, cwd):
    """`p` (realpath) a SAJÁT projekt auto-memóriája (a session_dir szerint): <gyökér>/projects/<saját>/
    memory/ maga, vagy egy közvetlenül benne lévő .md (nem mappa, nem többszörös hardlink). Más projekt
    memóriája, az átiratok és minden mélyebb út nem az (11-08)."""
    own = session_dir(cwd) if cwd else None
    return bool(own and p) and _mem_match(p, _project_dirs(own))


def cd_memory(p, cwd):
    """A cwd szerint saját lenne, a session projektje szerint nem: `cd` egy másik projektbe."""
    return bool(cwd and p) and not own_memory(p, cwd) and _mem_match(p, _project_dirs(cwd))


def in_transcripts(p, cwd=None):
    """Egy ~/.claude*/projects/ alatt: az egész titoktár, csak a saját projekt memory/ mappája kivétel."""
    for r in claude_roots():
        proj = os.path.join(r, "projects")
        if p == proj or p.startswith(proj + os.sep):
            return not own_memory(p, cwd)
    return False


def glob_hit(paths, pat):
    """Illik-e leltár-út a mintára úgy, ahogy a shell illesztené: a `*` nem lép át `/`-t (11-08: a
    `cwd/*` a cwd alatti BÁRMELY mélységű leltár-fájlra illett). `**` esetén marad az átlépő illesztés."""
    if "**" in pat:
        return any(fnmatch.fnmatch(x, pat) for x in paths)
    ps = pat.split(os.sep)
    return any(len(xs) == len(ps) and all(fnmatch.fnmatch(a, b) for a, b in zip(xs, ps))
               for xs in (x.split(os.sep) for x in paths))


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


#: A Telegram-híd naplómappái (11-09): `~/.config/<ágens>/telegram-inbox/` (events-*.jsonl,
#: delivery-*.jsonl) és `~/.config/<ágens>/sub-etha/` (a híd kódja). A napló üzenetszöveg és
#: Telegram-update, kulcs nem: a bot-token csak a hívás URL-jében él (fleet/bridge/lib/inbox.mjs,
#: delivery-log.mjs). Csak az ártalmatlan nevű, SEMMIRE nem illő `*.jsonl` minta mentes; a token- és
#: env-fájlok, más kiterjesztés vagy mappa marad tiltva, az illő fájlokat a kapu egyenként nézi.
BRIDGE_LOG_DIRS = ("sub-etha", "telegram-inbox")
LOG_GLOB = re.compile(r"^[A-Za-z0-9_.*?\-]*\.jsonl$")
LOG_SUSPECT = re.compile(r"key|token|secret|credential|passw|env", re.I)


def bridge_log_glob(p):
    """`p` (feloldott glob) a híd egyik naplómappájában álló, ártalmatlan nevű `*.jsonl` minta-e."""
    d, base = os.path.split(p)
    rel = os.path.relpath(d, home()).split(os.sep)
    return (len(rel) == 3 and rel[0] == ".config" and rel[2] in BRIDGE_LOG_DIRS and not rel[1].startswith(".")
            and bool(LOG_GLOB.match(base)) and not LOG_SUSPECT.search(base))


def name_why(base):
    """Erős név (.env, kulcs, credentials) szigorú; a csak szó-alapú (…key…, …token…) „gyanús":
    annak a tiltása mellé a kapu bejelentést kér, nem kerülőutat (11-07)."""
    if not name_hit(base):
        return None
    return "kulcsfájl-név" if STRONG.match(base) else "kulcsfájl-gyanús név"


def _skipped(x, skip, is_dir=False):
    """`x` (a keresés gyökeréhez képest relatív út) kimarad-e. `X`: X nevű mappa bárhol (alatta minden),
    `=X`: X nevű fájl bárhol, `./X`: pontosan ez a fájl, `./X/`: ami alatta van (titok_olvas._excludes)."""
    for k in skip or ():
        if k.startswith("./"):
            a = k[2:]
            if (x.startswith(a) if a.endswith("/") else (x == a and not is_dir)):
                return True
        elif k.startswith("="):
            if not is_dir and os.path.basename(x) == k[1:]:
                return True
        elif k in x.split(os.sep)[:-1] or (is_dir and os.path.basename(x) == k):
            return True
    return False


def _file(p, lel, rec, skip=(), cwd=None):
    if lel.has(p):
        return "leltárban"
    if in_transcripts(p, cwd):
        if cd_memory(p, cwd):
            return "más projekt memóriája: a cwd (%s) nem a session projektje (%s); a `cd` nem teszi sajáttá" % (
                cwd, session_dir(cwd))
        return "átirat"
    if re.match(r"^/proc/[^/]+/environ$", p):
        return "környezet"
    if os.path.isdir(p):
        return _tree(p, lel, skip, cwd) if rec else None
    return name_why(os.path.basename(p))


def _tree(d, lel, skip=(), cwd=None):
    """`skip`: a parancs saját kizárásai (grep --exclude-dir=X / --exclude=X): amit a parancs
    kihagy, azt nem olvassa — ezért a találat sem tilt (11-07: a `grep -r minta .` egy
    `…_keys.sql` migráció miatt tiltott, és nem volt kiút)."""
    dd = d.rstrip(os.sep) + os.sep
    if any(x.startswith(dd) and not _skipped(x[len(dd):], skip) for x in lel.paths):
        return "leltárban (mappa: %s)" % _first(d, [x for x in lel.paths if x.startswith(dd)][0])
    if holds_transcripts(d) or in_transcripts(d, cwd):
        return "átiratokat tartalmazó mappa"
    n = 0
    for root, dirs, files in os.walk(d):
        rel = os.path.relpath(root, d)
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "__pycache__", ".venv")
                   and not _skipped(os.path.normpath(os.path.join(rel, x)), skip, True)]
        n += len(files) + len(dirs)
        if n > WALK_BUDGET:
            return "túl nagy mappa, nem ellenőrizhető"
        hit = next((f for f in files if not _skipped(os.path.normpath(os.path.join(rel, f)), skip) and name_hit(f)),
                   None)
        if hit or (in_transcripts(root, cwd) and any(f.endswith(".jsonl") for f in files)):
            return "kulcsfájl a mappában (%s)" % _first(d, os.path.join(root, hit or ""))
        link = next((f for f in files + dirs if _link_out(os.path.join(root, f), lel, cwd)), None)
        if link:  # `grep -R` követi: a mappába tett symlink se vigyen átiratra/leltár-fájlra
            return "titokra mutató symlink a mappában (%s)" % _first(d, os.path.join(root, link))
    return None


def _link_out(x, lel, cwd):
    if not os.path.islink(x):
        return False
    t = os.path.realpath(x)
    return lel.has(t) or in_transcripts(t, cwd) or holds_transcripts(t)


def _first(d, x):
    """A találat első mappája a `d` alatt (név, érték nélkül): ezt lehet --exclude-dir-rel kizárni."""
    rel = os.path.relpath(x, d).split(os.sep)
    return rel[0] if rel and rel[0] not in (".", "") else os.path.basename(d.rstrip(os.sep)) or d


def resolve(path, cwd):
    p = path.replace("${HOME}", "~").replace("$HOME", "~")
    if "$" in p or "`" in p:
        return None
    return os.path.realpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(p)))


def _stores():
    """A titoktár-gyökerek: ~/.config, ~/.mentat, ~/.ssh és minden Claude-gyökér."""
    return [os.path.join(home(), d) for d in (".config", ".mentat", ".ssh")] + claude_roots()


def _static(path, cwd):
    """A biztosan ismert kifejezések behelyettesítése: $PWD, $(pwd), $CLAUDE_PROJECT_DIR, a git-gyökér."""
    top = next((d for d in sorted(_project_dirs(cwd), key=len) if os.path.exists(os.path.join(d, ".git"))),
               cwd) if cwd else None
    for pat, val in ((r"\$\(\s*git\s+rev-parse\s+--show-toplevel\s*\)", top), (r"\$\(\s*pwd\s*\)", cwd),
                     (r"\$(?:\{PWD\}|PWD(?!\w))", cwd),
                     (r"\$(?:\{CLAUDE_PROJECT_DIR\}|CLAUDE_PROJECT_DIR(?!\w))", os.environ.get("CLAUDE_PROJECT_DIR"))):
        if val:
            path = re.sub(pat, lambda _m, v=val: v, path)
    return path


def _unresolved(path, cwd, lel):
    """`$X`/$(…)/`…` maradt az útban (futásidejű érték). Tilt, ha a statikus előtag mappája titoktárban
    van (~/.claude*, ~/.config, ~/.mentat, ~/.ssh) vagy afölött (HOME, /), illetve egy leltár-fájl
    mappája. Üres előtag (`cat "$F"`) átmegy: szándékos megkerülés ellen a kapu nem véd (az az OS-izoláció dolga)."""
    pre = re.split(r"[$`]", path.replace("${HOME}", "~").replace("$HOME", "~"), maxsplit=1)[0]
    if not pre:
        return None
    base = resolve(pre if pre.endswith("/") else os.path.dirname(pre) or ".", cwd)
    if not base:
        return None
    st = _stores()
    inside = any(base == x or base.startswith(x + os.sep) for x in st)
    above = any(x.startswith(base.rstrip(os.sep) + os.sep) for x in st)
    if inside or above or any(os.path.dirname(x) == base for x in lel.paths):
        return "futásidejű út titoktárban (%s), adj meg konkrét útvonalat" % (pre.replace(home(), "~", 1) or ".")
    return None


def secret(path, cwd, lel, rec=False, skip=()):
    path = _static(path, cwd)
    p = resolve(path, cwd)
    if p is None:
        return _unresolved(path, cwd, lel)
    if not GLOB.search(p):
        return _file(p, lel, rec, skip, cwd)
    hits = glob.glob(p)[:500]
    for h in hits:
        why = _file(os.path.realpath(h), lel, rec, skip, cwd)
        if why:
            return why
    if glob_hit(lel.paths, p):
        return "leltárban (glob)"
    if not hits and own_memory(os.path.dirname(p), cwd):
        return None
    if not hits and bridge_log_glob(p):  # a híd üzenetnaplója (11-09)
        return None
    if not hits and (secret_root(os.path.dirname(p)) or in_transcripts(os.path.dirname(p), cwd)):
        return "titok-mappa (glob)"
    return name_why(os.path.basename(p)) if not hits else None
