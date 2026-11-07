"""Az identitás-kapu helyi állapota: a SessionStart-cache és a védett fájlok (F-41).

    save(cwd)            SessionStart: az azonosítók és a saját GitHub-login a cache-be (0600)
    load(cwd) -> (Ids, logins)   PreToolUse: a cache-ből, alprocessz nélkül; ha nincs, élő olvasás
    touches_protected(tool, inp, cwd) -> path | None   az ágens nem írhatja a kapu fájljait (vedett.py)
    user_gate_active() -> bool   fut-e a felhasználói szintű kapu (a plugin-példány ekkor hátrébb lép)

A cache, a `identitas.txt` és az `elsofel.txt` a `~/.mentat/` alatt él. Ha az ágens
kiürítené a cache-t vagy bővítené az allowlistet, a kapu vakká válna; ezért ezekre minden
író hívás tilos, és a cache-t a kapu a repó e-mailjével is kiegészíti minden híváskor.
"""
import json
import os
import re

import ident
import vedett

DIR = os.path.expanduser("~/.mentat")
CACHE = os.path.join(DIR, "identitas-cache.json")
ERRLOG = os.path.join(DIR, "identitas-kapu-hibak.jsonl")


def save(cwd):
    ids = ident.load(extra_dirs=[cwd or "."], gh=True)
    login = ident._run(["gh", "api", "user", "-q", ".login"])
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    tmp = CACHE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"ids": ids.values, "gh_logins": [login] if login else []}, f)
    os.replace(tmp, CACHE)


def load(cwd):
    try:
        with open(CACHE) as f:
            d = json.load(f)
        repo = ident._run(["git", "-C", cwd or ".", "config", "user.email"])
        return ident.Ids(d.get("ids", []) + [repo] + ident._extra()), d.get("gh_logins", [])
    except (OSError, ValueError):
        return ident.load(extra_dirs=[cwd or "."], gh=False), []


def touches_protected(tool, inp, cwd=None):
    """Az ágens ÍRÁSA a kapu fájljaira, kódjára vagy a felhasználói Claude-beállításra (vedett.py).
    Balesetvédelem: ugyanaz az OS-felhasználó szándékosan megkerülheti; a tartós határ a külön
    user (F-38). A `beallitas:` előtagú találatot a hook kérdezi (a user kérheti), a többit tiltja."""
    return vedett.protected_write(tool, inp, cwd)


def log_error(phase, e, command):
    """One JSON line per analysis failure: when, where in the code, and a hash of the call — never its text."""
    import hashlib
    import time
    import traceback
    tb = traceback.extract_tb(e.__traceback__)[-1:] or [None]
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": type(e).__name__,
           "where": "%s:%s" % (os.path.basename(tb[0].filename), tb[0].lineno) if tb[0] else "?",
           "sha256": hashlib.sha256(str(command).encode()).hexdigest()[:16]}
    try:
        os.makedirs(DIR, mode=0o700, exist_ok=True)
        with open(ERRLOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def user_gate_active():
    """Fut-e ebben a sessionben az ellenőrzött, felhasználói szintű kapu (TELEPITES-MAC.md)?
    A repón kívüli `settings.json`-t nézi (CLAUDE_CONFIG_DIR vagy ~/.claude), és a kód meglétét.
    Az ágens ezeket nem írhatja kérdés nélkül, a repón belüli jelzőt viszont igen; ezért csak ez
    alapján lép hátrébb a plugin- és a bootstrap-példány, fordítva soha."""
    conf = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(conf, "settings.json")) as f:
            pre = (json.load(f).get("hooks") or {}).get("PreToolUse") or []
    except (OSError, ValueError, AttributeError):
        return False
    for e in pre:
        for h in e.get("hooks") or []:
            cmd = str(h.get("command", ""))
            m = re.search(r"(/\S*identitas-kapu/current/kapu\.py)\s+--hook", cmd)
            if m and h.get("onFailure") == "block" and e.get("matcher") in ("*", None) \
                    and os.path.isfile(os.path.expanduser(m.group(1))):
                return True
    return False
