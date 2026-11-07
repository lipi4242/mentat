"""The capability tree going out and coming in (phase 3): what this agent shows the fleet, and
what the fleet answers. Both sides treat the other's text as untrusted data.

    export(root, brain)       -> {capabilities: [{id, availability, provenance, intent}], own_hidden}
    fleet_find(root, query)   -> (candidates, meta) or ([], None) when no fleet is installed

Export: only the approved fields. Suite items go out (the catalog is public anyway). An own item
goes out only if the USER listed its id in ~/.mentat/kepessegfa-megosztas.txt (outside the repo;
the guard never lets the agent write it), and only if its text passes the leak check: the
takeover filter's patterns (bekotes/szuro.py: secret, e-mail, IBAN, tax number, phone, IP, home
path) plus URLs; otherwise it is counted. Without szuro.py nothing own goes out and nothing comes in. Fleet answers: asked through
`fleet capabilities find --as <agent> --json "<request>"`; every item is checked (id pattern,
known values, short clean text) and the rest dropped. A hit gives the way to ask, never access.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(_HERE / "bekotes"), str(_HERE.parent / "bekotes")]  # installed / dev layout
try:
    import szuro  # noqa: E402  the takeover filter: one set of patterns for what may leave
except ImportError:
    szuro = None

SHARE = os.path.join("~", ".mentat", "kepessegfa-megosztas.txt")
URL = re.compile(r"https?://|\bwww\.", re.I)
ID = re.compile(r"^[a-z][a-z0-9._-]{1,80}$")
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,40}$")
AVAIL = {"on", "degraded", "available", "off", "unknown"}
PROV = {"suite", "own", "external"}


def _leaks(t, inbound=False):
    if szuro is None:
        return True
    return bool(szuro.redact(t)[1]) or bool(URL.search(t)) or (inbound and szuro.suspicious(t))


def clean(texts, inbound=False):
    """(kept texts, leaked?) — each text a short string without anything that identifies."""
    out, leaked = [], False
    for t in texts if isinstance(texts, list) else []:
        if not isinstance(t, str):
            continue
        if _leaks(t, inbound):
            leaked = True
            continue
        out.append(" ".join(t.split())[:60])
    return out[:3], leaked


def _shared():
    try:
        with open(os.path.expanduser(SHARE), encoding="utf-8", errors="replace") as f:
            return {ln.split("#", 1)[0].strip() for ln in f if ln.split("#", 1)[0].strip()}
    except OSError:
        return set()


def export(index, prober, lang):
    shared, items, hidden, dropped = _shared(), [], {}, []
    for e in index["entries"]:
        own = e["provenance"] != "suite"
        if own and e["id"] not in shared:
            hidden[e["category"]] = hidden.get(e["category"], 0) + 1
            continue
        texts = ([e["summary"]["hu"]] if own else []) + [p for l_ in ("hu", "en") for p in e["intents"].get(l_, [])]
        intent, leaked = clean(texts)
        if leaked and own or own and szuro is None:
            dropped.append(e["id"])
            continue
        items.append({"id": e["id"], "availability": prober.state(e["id"])["availability"],
                      "provenance": e["provenance"], "intent": intent})
    for d in dropped:
        print("kihagyva (szivárgás-ellenőrzés): %s" % d, file=sys.stderr)
    return {"schema": 1, "index": {"version": index["version"], "hash": index["hash"]},
            "capabilities": items, "own_hidden": hidden, "own_dropped": len(dropped)}


def _agent(root):
    try:
        with open(os.path.join(str(root), ".mentat", "local.json"), encoding="utf-8") as f:
            fl = json.load(f).get("fleet")
        return fl.get("agent_id") if isinstance(fl, dict) and isinstance(fl.get("agent_id"), str) else None
    except (OSError, ValueError, AttributeError):
        return None


def fleet_find(root, query):
    agent = _agent(root)
    if not agent or not shutil.which("fleet"):
        return [], None
    try:
        r = subprocess.run(["fleet", "capabilities", "find", "--as", agent, "--json", query],
                           capture_output=True, text=True, timeout=8)
        results = json.loads(r.stdout).get("results") if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        results = None
    if not isinstance(results, list):
        return [], {"asked": True, "error": "the fleet did not answer"}
    kept, dropped = [], 0
    for x in results:
        ok = isinstance(x, dict) and NAME.match(str(x.get("agent", ""))) and ID.match(str(x.get("id", ""))) \
            and x.get("availability") in AVAIL and x.get("provenance") in PROV
        intent, leaked = clean(x.get("intent") if ok else [], inbound=True)
        if not ok or leaked:
            dropped += 1
            continue
        kept.append({"id": "external.fleet.%s.%s" % (x["agent"], x["id"]), "category": "fleet",
                     "summary": "; ".join(intent) or x["id"], "intents": {"hu": intent, "en": []},
                     "provenance": "external", "lifecycle": "active", "scope": "fleet",
                     "availability": x["availability"], "agent": x["agent"],
                     "entry": "fleet:request %s \"<a kérés>\" (az övé: kérni lehet, használni nem)" % x["agent"]})
    return kept, {"asked": True, "kept": len(kept), "dropped": dropped}
