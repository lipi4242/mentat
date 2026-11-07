"""A titok-kapu kód- és környezet-szabályai (titok_olvas.py használja).

    code(text, cwd, lel)   értelmezőnek adott kód (-c, -e, heredoc): környezet-kiírás, vagy titokra
                           mutató szövegliterál (út, vagy kulcsfájl-név mint ".env")
    envdump(name, args)    a parancs kiírja-e a környezetet: bare env, printenv, set, export -p,
                           ps e/eww, systemctl … show-environment
    search_args(name, args)  grep/rg/ag-nál a keresett MINTA nem út: kiveszi, a -f/--file fájlját meghagyja
"""
import os
import re

from titok_minta import name_hit, secret
from vedett_ut import STRINGS

#: Azonosító alakú literál (`owner_token`, `api_key`): mezőnév vagy változónév, nem fájlnév — csak akkor
#: tilt, ha ilyen nevű fájl tényleg ott van a cwd-ben (élő hiba, 2026-11-07: a heartbeat `owner_token` mezője).
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PROC = re.compile(r"/proc/[^\s'\"]*/environ")
ENVDUMP = re.compile(r"/proc/[^\s'\"]*/environ|\bprint\(\s*(dict\()?os\.environ\s*\)?\)|"
                     r"json\.dumps\(\s*(dict\()?os\.environ|JSON\.stringify\(\s*process\.env\s*\)|"
                     r"console\.log\(\s*process\.env\s*\)|os\.environ\.items\(\)")


def code(text, cwd, lel):
    """Értelmezőnek adott kód: környezet-kiírás, vagy titokra mutató szövegliterál."""
    if ENVDUMP.search(text):
        return "környezet kiírása"
    for m in STRINGS.finditer(text):
        lit = next(g for g in m.groups() if g is not None)
        if "\n" in lit or not lit.strip():
            continue
        if "/" in lit or lit.startswith("~"):
            why = secret(lit, cwd, lel)
            if why:
                return why
        elif name_hit(os.path.basename(lit)):
            # Azonosító (`owner_token`) vagy szóközös szabad szöveg („a Linear app-token kivezetése”):
            # mezőnév vagy mondat, nem fájlnév — csak akkor tilt, ha ilyen nevű fájl tényleg van.
            if (IDENT.match(lit) or any(c.isspace() for c in lit)) and \
                    not os.path.lexists(os.path.join(cwd or ".", lit)):
                continue
            return "kulcsfájl-név a kódban"
    return None


def envdump(name, args):
    if name == "env":
        rest, skip = [], False
        for a in args:
            if skip:
                skip = False
            elif a in ("-u", "--unset", "-C", "--chdir", "-S"):
                skip = True
            elif not (a.startswith("-") or re.match(r"^\w+=", a)):
                rest.append(a)
        return None if rest else "környezet kiírása (env)"
    if name == "printenv" or (name == "set" and not args) or (name in ("export", "declare") and
                                                            (not args or "-p" in args or "-x" in args)):
        return "környezet kiírása (%s)" % name
    if name == "ps" and any(not a.startswith("-") and "e" in a for a in args):
        return "környezet kiírása (ps e)"
    if name in ("systemctl", "launchctl") and any("environment" in a.lower() for a in args):
        return "környezet kiírása (%s)" % name
    return None



SEARCHERS = {"grep", "egrep", "fgrep", "zgrep", "rg", "ag"}
VALUE_OPTS = {"-m", "-A", "-B", "-C", "-d", "-D", "-g", "-t", "-T", "-j", "-M", "--max-count", "--context",
              "--after-context", "--before-context", "--glob", "--iglob", "--type", "--type-not", "--max-depth"}


def search_args(name, args):
    """A keresőparancs argumentumai a minta nélkül: a minta szöveg, nem fájl (a `"lease_token": *"…"`
    a mezőnevet keresi, kulcsfájlt nem nyit; Kata, 2026-10-31). A -f/--file fájlja olvasás, az marad."""
    if name not in SEARCHERS:
        return args
    out, pos, explicit, skip, value, dashdash = [], [], False, False, False, False
    for a in args:
        if skip:
            skip = False
        elif value:
            value = False
            out.append(a)
        elif not dashdash and a == "--":
            dashdash = True
        elif not dashdash and a.startswith("-") and a != "-":
            short = not a.startswith("--")
            if a in ("-e", "--regexp"):
                explicit = skip = True
                continue
            if a.startswith("--regexp=") or (short and a.startswith("-e")):
                explicit = True
                continue
            if a in ("-f", "--file") or a.startswith("--file=") or (short and a.startswith("-f")):
                explicit = True
            value = a in VALUE_OPTS
            out.append(a)
        else:
            pos.append(a)
    return out + (pos if explicit else pos[1:])
