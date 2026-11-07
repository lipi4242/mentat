"""A nem-akadó hook állapota: a felügyelet nélküli mód jelzői és a megtagadások naplója.

A jelzőfájl (`~/.mentat/felugyelet-nelkul`) első sora a lejárat epoch-másodpercben. A napló
(`~/.mentat/nemakad-naplo.jsonl`, 0600) soronként egy megtagadás, csak maszkolt előtaggal:
teljes parancs soha nem kerül bele, mert tokent tartalmazhat.
"""
import datetime
import json
import os
import time

import nemakad_alak as alak

ENV_JELEK = ("MENTAT_HEADLESS", "FLEET_AGENT", "THUFIR_AGENT")
NAPLO_MAX = 1 << 20


def _mentat():
    return os.path.join(os.path.expanduser("~"), ".mentat")


def jelzo():
    return os.path.join(_mentat(), "felugyelet-nelkul")


def naplo_ut():
    return os.path.join(_mentat(), "nemakad-naplo.jsonl")


def mod(now=None, cwd=None):
    """(felügyelet_nélkül: bool, ok: str). A cwd a hívásé (a hook bemenetéből), lehet None."""
    for k in ENV_JELEK:
        if os.environ.get(k):
            return True, "env:" + k
    try:
        if isinstance(cwd, str) and cwd and os.path.isfile(os.path.join(cwd[:4096], ".claude", "fleet.json")):
            return True, "repo: .claude/fleet.json"
    except Exception:  # noqa: BLE001 - fura út: ettől a jelzőtől függetlenül döntünk tovább
        pass
    now = time.time() if now is None else now
    try:
        with open(jelzo(), encoding="utf-8", errors="replace") as f:
            first = f.readline(200).strip()
    except FileNotFoundError:
        return False, "nincs jelző"
    except Exception:  # noqa: BLE001 - van jelző, de nem olvasható: a deny a biztonságos irány
        return True, "jelző olvashatatlan"
    try:
        lejar = float(first.split()[0])
    except (ValueError, IndexError):
        return True, "jelző értelmezhetetlen"
    if lejar != lejar:  # NaN
        return True, "jelző értelmezhetetlen"
    if lejar > now:
        return True, "jelző eddig: " + datetime.datetime.fromtimestamp(min(lejar, 3e10)).strftime("%m-%d %H:%M")
    return False, "jelző lejárt"


def naploz(data, tool, shape):
    try:
        p = naplo_ut()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p) and os.path.getsize(p) > NAPLO_MAX:
            os.replace(p, p + ".1")
        sor = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool[:60],
               "alak": shape, "eloszo": alak.prefix(data.get("tool_input")),
               "cwd": alak.mask(str(data.get("cwd") or ""))}
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(sor, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - a napló hibája soha nem állíthatja meg a deny-t
        pass


def alszom(ido="08:00", now=None):
    now = datetime.datetime.now() if now is None else now
    h, m = (int(x) for x in ido.split(":"))
    cel = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if cel <= now:
        cel += datetime.timedelta(days=1)
    os.makedirs(_mentat(), exist_ok=True)
    with open(jelzo(), "w", encoding="utf-8") as f:
        f.write("%d %s\n" % (cel.timestamp(), cel.isoformat(timespec="minutes")))
    return cel


def naplo(orak=24.0):
    hatar = datetime.datetime.now() - datetime.timedelta(hours=orak)
    try:
        with open(naplo_ut(), encoding="utf-8", errors="replace") as f:
            sorok = f.readlines()
    except FileNotFoundError:
        return []
    out = []
    for s in sorok:
        try:
            d = json.loads(s)
            if datetime.datetime.fromisoformat(d["ts"]) >= hatar:
                out.append("%s  %s  %s  %s" % (d["ts"][5:16], d["tool"], d["alak"], d["eloszo"]))
        except Exception:  # noqa: BLE001 - egy sérült sor ne vigye el a jelentést
            continue
    return out
