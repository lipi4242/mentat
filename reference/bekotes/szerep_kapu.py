"""Operations that need the USER, whatever the role (szerep_dontes asks or denies them).

protected(root, tool, inp, cwd) -> path: the consent list, the log, a capability receipt or the
                                  identity gate's files are touched (always deny).
dangerous(root, tool, inp, cwd) -> [kind]: kinds below (ask interactively, deny headless).
The later gates (szerep_kapu_kepesseg, szerep_kapu_id, szerep_kapu_szerver) are wired in _later(), one place.
"""
import os
import re

from szerep_bash import _args, analyse, commands
from szerep_kapu_db import writes as db_writes
from szerep_kapu_git import _git
from szerep_engedely import LIST
from szerep_kint import WRITERS, real, under
from szerep_naplo import LOG

KINDS = {
    "rm-kivul": "rekurzív vagy kényszerített törlés a munkamappán kívül",
    "force-push": "git push --force (felülírja a távoli történetet)",
    "titok": ".env vagy kulcsfájl tartalmának olvasása",
    "post": "adatküldés (curl/wget POST) egy külső címre",
    "env": "biztonsági környezeti változó felülírása (GIT_NO_LAZY_FETCH, MENTAT_ROLE, HOME, …)",
    "git-config": "git-beállítás felülírása (-c, config, sparse-checkout)",
    "db-iras": "adatbázis-írás közvetlenül a parancssorból (wrangler d1, sqlite3, psql, mysql), az alkalmazás útja helyett",
    "uj-kepesseg": "új futtatható kód, unit, ütemezés vagy új csomag friss képesség-nyugta nélkül — előbb "
                   "`python3 .mentat/bin/mentat_brain.py where --find \"<a kérés>\"`, aztán `where --decide`",
    "identitas": "a FELHASZNÁLÓ azonosítója (e-mail) harmadik félhez menne; hagyd ki: a polite-pool, a "
                 "User-Agent és a mailto mező üresen marad, az API-k nélküle is működnek",
    "elsofel": "a saját helyek listájának (elsofel.txt a ~/.mentat alatt) bővítése a parancsban felsorolt sorokkal",
    "szerver": "szerver vagy soha véget nem érő parancs (előtérben vagy run_in_background) blokkolja a fordulót — futtasd egyszer (`tail -n 50`, `ping -c 3`, `up -d`), vagy: `python3 .mentat/bin/mentat_serve.py start <név> --dir <mappa> | [--port <port>] -- <parancs>`",
    "beallitas": "a szerep-őr kódjának, mappáinak, a hook-beállításnak (.claude/settings*.json) vagy egy PATH-on futó értelmezőnek a cseréje",
}
SECRET = re.compile(r"^(\.env.*|.*\.(pem|key|p12|pfx)|id_(rsa|dsa|ecdsa|ed25519).*|\.netrc|\.npmrc|"
                    r"\.pypirc|credentials(\.json)?|\.credentials\.json|claude-auth\.env)$", re.I)
TEXT = {"echo", "printf", ".", "source", "ls", "stat", "test", "[", "chmod"}  # words, a source or metadata: not the content
OWN = {"mentat_serve.py", "mentat_secret.py"}  # the product's own secret route (szerep_dontes names it)
VARS = (r"(GIT_NO_LAZY_FETCH|MENTAT_ROLE|CLAUDE_CONFIG_DIR|CLAUDE_PROJECT_DIR|HOME|GIT_DIR|GIT_SSH_COMMAND|GIT_CONFIG\w*|"
        r"CLOUDFLARE_API_BASE_URL|CLOUDFLARE_API_BASE|MENTAT_CF_API_ALLOW_HOST)")  # the token's endpoint: the environment's
ENV = [re.compile(r"(?:^|[\s;&|(`])%s=" % VARS),
       re.compile(r"\b(?:export|unset|declare|typeset|readonly|local)\s+(?:-\w+\s+)*%s\b" % VARS),
       re.compile(r"\benv\s+(?:-\S+\s+)*-u\s*%s\b" % VARS)]
ROLE_CLI = re.compile(r"\s*MENTAT_ROLE=\S+\s+python3\s+\.mentat/bin/mentat_cli\.py\s+role(\s+--json)?\s*")
GUARD_CODE = (".mentat/bin", ".claude/settings.json", ".claude/settings.local.json")  # the guard and the product's tools
REFRESH = "cp .mentat/bin/bekotes/mentat_*.py .mentat/bin/"  # BEKOTES step 0, verbatim
DATA = ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-F", "--form",
        "-T", "--upload-file", "--json", "--post-data", "--post-file")
LOCAL, REPLACERS = ("localhost", "127.0.0.1", "[::1]"), {"mv", "rm", "rmdir", "ln", "unlink", "rsync"}
EXECS = {"python3", "python", "sh", "bash", "zsh", "env", "node"}  # what the hooks run via PATH


def _written(tool, inp, cwd):
    if tool in WRITERS:
        return [os.path.join(cwd, str(inp.get("file_path") or inp.get("notebook_path") or ""))]
    return analyse(str(inp.get("command", "")), cwd)[1] if tool == "Bash" else []


def _hits(p, targets, root, parents=False):
    """p is a target or inside one; with parents, also a folder above one (not the repo)."""
    f = real(p)
    return any(under(f, g) or (parents and f != real(root) and under(g, f)) for g in targets)


def _replaced(cmd, cwd):
    """Folders a Bash command moves, removes or relinks (`mv .mentat x`, `rm -rf .claude`)."""
    return [os.path.join(wd or ".", os.path.expanduser(a)) for name, words, wd, _, _ in commands(cmd, cwd)
            if name in REPLACERS for a in _args(words)]


def _later(root, tool, inp, cwd, which):
    import szerep_kapu_id as ident  # lazy: both import this module's helpers
    import szerep_kapu_kepesseg as kep
    if which == "protected":
        return kep.touched(root, tool, inp, cwd) or ident.protected(tool, inp, cwd, root) or \
            __import__("szerep_kapu_final").touched(root, tool, inp, cwd)
    inline = __import__("szerep_kapu_inline")
    return (["uj-kepesseg"] if kep.needs(root, tool, inp, cwd) else []) + \
        (["beallitas"] if inline.guard_write(tool, inp) else []) + (["post"] if inline.mail(tool, inp) else []) + \
        (["identitas"] if ident.needs(root, tool, inp, cwd) else []) + \
        (["elsofel"] if ident.writes_allowlist(tool, inp) else []) + \
        (["szerver"] if __import__("szerep_kapu_szerver").blocks(tool, inp, cwd) else [])


def protected(root, tool, inp, cwd):
    later = _later(root, tool, inp, cwd, "protected")
    if later:
        return later
    mine = [real(os.path.join(root, LIST)), real(os.path.join(root, os.path.dirname(LOG)))]
    cmd = str(inp.get("command", "")) if tool == "Bash" else ""
    for p in _written(tool, inp, cwd) + [(x, True) for x in _replaced(cmd, cwd)]:
        p, parents = p if isinstance(p, tuple) else (p, False)
        if _hits(p, mine, root, parents):
            return p
    cmd = str(inp.get("command", "")).lower()
    if tool == "Bash" and ("engedelyek" in cmd or "naplo/kivuli" in cmd) and "szerep_engedely.py lista" not in cmd:
        return LIST  # python -c, ln, … : the list is not the agent's to touch
    return None


def _not_own(words):
    """Words the secret check reads: all but the product's own secret tool's own arguments (mentat_serve
    before `--`; mentat_secret put/has). What runs after `--` is checked as its own command too."""
    own = next((i for i, w in enumerate(words) if os.path.basename(w) in OWN), None)
    if own is None or (os.path.basename(words[own]) == "mentat_secret.py" and words[own + 1:own + 2] not in (["put"], ["has"])):
        return words[1:]
    return words[words.index("--") + 1:] if "--" in words[own:] else []


def _bash(root, cmd, cwd):
    out = ["env"] if any(r.search(cmd) for r in ENV) and not ROLE_CLI.fullmatch(cmd) else []
    for name, words, wd, _, _ in commands(cmd, cwd):
        args = _args(words)
        if name == "git":
            out += _git(words, root, wd)
        if name == "rm" and any(w.startswith("-") and set(w) & set("rRf") for w in words[1:]):
            if any(not under(real(os.path.join(wd or ".", os.path.expanduser(a))), real(root)) for a in args):
                out.append("rm-kivul")
        if name in ("curl", "wget"):
            sends = any(w in DATA or w.startswith(tuple(d + "=" for d in DATA)) for w in words) or any(
                re.fullmatch(r"(-X|--request|--method)=?(POST|PUT|PATCH|DELETE)?", w, re.I) for w in words)
            urls = [w for w in args if "://" in w or re.match(r"[\w.-]+\.\w+(/|$)", w)]
            if sends and any(not re.sub(r"^\w+://", "", u).startswith(LOCAL) for u in urls or ["?"]) and \
                    not __import__("szerep_kapu_final").approved_send(root, words, wd):
                out.append("post")
        if name not in TEXT and any(SECRET.match(os.path.basename(w.rstrip("/"))) for w in _not_own(words)):
            out.append("titok")
        if db_writes(name, words, wd):
            out.append("db-iras")
    return out


def dangerous(root, tool, inp, cwd):
    out = _bash(root, str(inp.get("command", "")), cwd) if tool == "Bash" else []
    if tool in ("Read", "NotebookRead", "Grep", "Glob"):
        named = [inp.get("file_path"), inp.get("notebook_path"), inp.get("path"), inp.get("glob"), inp.get("pattern") if tool == "Glob" else None]
        if any(n and SECRET.match(os.path.basename(str(n).rstrip("/"))) for n in named):
            out.append("titok")
    guard = [real(os.path.join(root, g)) for g in GUARD_CODE]
    path_dirs = {real(d) for d in os.environ.get("PATH", "").split(os.pathsep) if d}
    refresh = REFRESH in str(inp.get("command", "")) and real(os.path.join(root, ".mentat", "bin"))
    for p in _written(tool, inp, cwd):
        if p.endswith(("${f#*/}", "/#1")) or (refresh and real(p) == refresh):  # BEKOTES step 0, init step 1
            continue
        if _hits(p, guard, root) or (os.path.basename(p) in EXECS and real(os.path.dirname(p)) in path_dirs):
            out.append("beallitas")
    if tool == "Bash" and any(_hits(p, guard, root, True) for p in _replaced(str(inp.get("command", "")), cwd)):
        out.append("beallitas")
    return list(dict.fromkeys(out + _later(root, tool, inp, cwd, "dangerous")))
