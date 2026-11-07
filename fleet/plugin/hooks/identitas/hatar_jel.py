"""Az ágens-határ összeolvasztás-módjának jelzője és hibanaplója (CISO Q2/Q5, 2026-10-29).

    aktiv(now=None) -> bool   él-e a ~/.mentat/titkok/hatar-aktiv jelző (JSON: since, until, reason, set_by)
    naplo(sor)                egy sor a ~/.mentat/titkok/hatar-hibak.log-ba (titokérték soha)

A jelzőt csak a `fleet secrets merge-mode` írja (a `plan-merge`, a `hold-outward` és a két- vagy
többágenses `secrets scan` ezt hívja). A titkok mappáját a titok-kapu védi az Edit/Write-tól.
Lejárt, hibás, vagy 7 napnál hosszabb jelző = nincs összeolvasztás-mód.
"""
import json
import os
import time

MAX_S = 7 * 86400


def _dir():
    return os.path.join(os.path.realpath(os.path.expanduser("~")), ".mentat", "titkok")


def path():
    return os.path.join(_dir(), "hatar-aktiv")


def aktiv(now=None):
    now = time.time() if now is None else now
    try:
        with open(path()) as f:
            d = json.load(f)
        since, until = float(d["since"]), float(d["until"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return since <= now + 60 and now < until and until - since <= MAX_S + 60


def naplo(sor):
    try:
        os.makedirs(_dir(), mode=0o700, exist_ok=True)
        fd = os.open(os.path.join(_dir(), "hatar-hibak.log"),
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "a") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), sor.replace("\n", " ")[:300]))
    except OSError:
        pass
