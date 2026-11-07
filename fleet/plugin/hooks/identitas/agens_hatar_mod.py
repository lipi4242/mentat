"""Ágens-határ, a módszer (H5-3 4. próba, 2026-10-29): a kerülőutak, amiket a szövegszintű tiltás után
a fejlesztő ágens választott.

- MINDIG: a flotta-registryt (a `FLEET_REGISTRY` vagy a ~/.config/fleet/registry mutató könyvtárában
  az agents.json, boxes.json) kézzel írni — `fleet registry set`; más repók fixtúrái szabadok;
- CSAK ÖSSZEOLVASZTÁS-MÓDBAN: más ágens fő ágát git-tel írni (merge, rebase, reset, cherry-pick, am,
  pull, commit, config-írás) vagy a `.git/`-jét szerkeszteni — a fogadó mergel, a tulajdonos neki adott
  👍-e után. Jelző nélkül ezek szabadok: a kiadó ágensek minden tickben így dolgoznak (CISO Q2).
A kapu kódjának olvasása nem tiltott: nyilvános kiadás után az csak rejtegetés lenne; az írása védett.
"""
import os
import re

import agens_hatar as A
import bash_szavak as S
import hatar_jel as J

GIT_WRITE = {"merge", "rebase", "reset", "cherry-pick", "am", "pull", "commit", "config"}
CONFIG_READ = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--get-urlmatch"}
REGISTRY = re.compile(r"\b(agents|boxes)\.json\b")
REG_MSG = "a flotta-registry kézi írása: `fleet registry set <ágens> <kulcs>=<érték> --owner-text …`"


def registry_dir():
    """A flotta registry-könyvtára (FLEET_REGISTRY, különben a mutatófájl), vagy None."""
    raw = os.environ.get("FLEET_REGISTRY", "").strip()
    if not raw:
        try:
            with open(os.path.join(A.home(), ".config", "fleet", "registry")) as f:
                raw = f.read().strip()
        except OSError:
            return None
    return os.path.realpath(os.path.expanduser(raw)) if raw else None


def _registry_file(a):
    d = registry_dir()
    return bool(d) and os.path.basename(a) in ("agents.json", "boxes.json") and os.path.dirname(a) == d


def file_tool(tool, p, cwd, merge):
    if tool == "Read":
        return None
    a = A._abs(p, cwd)
    if _registry_file(a):
        return REG_MSG
    r = A.agent_root(a)
    if merge and r and A.foreign(a, A.own_dir(cwd)) and A._inside(a, os.path.join(r, ".git")):
        return "másik ágens git-beállítása (%s)" % os.path.basename(r)
    return None


def _git(words, c):
    """(alparancs, repó-út) egy `git …` szakaszból; -C és -c argumentummal együtt."""
    repo, i = c, 1
    while i < len(words) and words[i].startswith("-"):
        if words[i] in ("-C", "-c") and i + 1 < len(words):
            repo = A._abs(words[i + 1], c) if words[i] == "-C" else repo
            i += 1
        i += 1
    return (words[i] if i < len(words) else ""), repo, words[i + 1:]


def bash(cmd, cwd, merge):
    cmd = S.subst(cmd)
    if REGISTRY.search(cmd) and any(_registry_file(a) for a in S.targets(cmd, cwd)):
        return REG_MSG
    if not merge:
        return None
    own = A.own_dir(cwd)
    for words, c in S.segments(cmd, cwd):
        if os.path.basename(words[0]) != "git":
            continue
        sub, repo, rest = _git(words, c)
        if sub not in GIT_WRITE or (sub == "config" and (CONFIG_READ & set(rest) or len(rest) < 2)):
            continue
        r = A.foreign(repo if os.path.isdir(repo) else c, own)
        if r and (sub == "config" or A._on_default_branch(r)):
            return ("git %s %s fő ágán: egy ágon dolgozol, a merge-et a fogadó végzi (`fleet ask`), a "
                    "tulajdonos neki adott 👍-e után" % (sub, os.path.basename(r)))
    return None


def decide(tool, inp, cwd, merge=None):
    merge = J.aktiv() if merge is None else merge
    if tool in ("Edit", "MultiEdit", "Write"):
        return file_tool(tool, str(inp.get("file_path") or ""), cwd, merge) if inp.get("file_path") else None
    if tool == "Bash":
        return bash(str(inp.get("command", "")), cwd, merge)
    return None
