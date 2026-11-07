"""`fleet capabilities` — a képességfa flotta-oldala (3. fázis, 2. PR).

    collect()                 ezen a boxon minden ágens jóváhagyott exportja → ~/.config/fleet/capabilities/
    collect_if_due()          naponta egyszer (a reconcile main-je hívja; hiba nem zavarja a reconcile-t)
    find(as_agent, query)     amit a kérdező láthat: ugyanazon a boxon a TÖBBI ágens tételei

Az ágens a saját repójában futtatja a bootstrap `where --export`-ját (csak id, availability,
provenance, intent; a saját tételt a user listája engedi, a bootstrap szivárgás-szűrője után).
Itt minden tétel nem megbízható adat: id-minta, ismert értékek, rövid szöveg, benne nincs @, URL,
home-út és öt számjegynél hosszabb számsor (telefon, adószám, IBAN, IP) — ami nem felel meg,
kiesik és megszámolódik. A láthatóság a lekérdezéskor érvényesül: egy box egy bizalmi zóna
(FL-04), más boxok tételei itt nem látszanak, a kérdező a saját tételeit nem kapja vissza, és a
suite-tételeket sem (azokat minden kereső maga is ismeri).
A találat a kérés útja (fleet:request), nem hozzáférés. Az állapot a repókon kívül él. Az ágens
kódja szűk környezetet kap (PATH, HOME, LANG, LC_ALL): a reconcile tokenjeit nem látja (F-33).
Korlát: a megosztási lista (~/.mentat/kepessegfa-megosztas.txt) a user HOME-jában él, így közös
OS-useres boxon minden ágensre egyszerre szól; ágensenkénti listát csak a külön OS-user ad (F-38).
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from fleet import CONFIG_DIR
from fleet.registry import agents_for_host, get_agent, load_agents, local_host

DIR = CONFIG_DIR / "capabilities"
DAY = 24 * 3600
ID = re.compile(r"^[a-z][a-z0-9._-]{1,80}$")
AVAIL = {"on", "degraded", "available", "off", "unknown"}
PROV = {"suite", "own", "external"}
UNSAFE = re.compile(r"@|://|\bwww\.|/(?:Users|home)/|\d[\d\s./-]{4,}\d")


class Refused(Exception):
    pass


def _workdir(e: dict) -> Path:
    return Path(str(e.get("workdir") or "").replace("%h", str(Path.home())))


def _valid(c) -> dict | None:
    if not (isinstance(c, dict) and isinstance(c.get("id"), str) and ID.match(c["id"])
            and c.get("availability") in AVAIL and c.get("provenance") in PROV):
        return None
    intent = c.get("intent") if isinstance(c.get("intent"), list) else []
    if any(not isinstance(t, str) or len(t) > 60 or UNSAFE.search(t) for t in intent):
        return None
    return {"id": c["id"], "availability": c["availability"], "provenance": c["provenance"],
            "intent": [" ".join(t.split()) for t in intent][:3]}


def _env() -> dict:
    """The agent's own code gets a narrow, explicit environment: never the reconcile's tokens (F-33)."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    return dict(env, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")


def _export(e: dict, timeout: int) -> dict:
    tool = _workdir(e) / ".mentat" / "bin" / "mentat_brain.py"
    if not tool.is_file():
        return {"error": "nincs mentat_brain.py az ágens repójában"}
    try:
        r = subprocess.run([sys.executable, "-I", str(tool), "--repo", str(_workdir(e)), "where", "--export"],
                           capture_output=True, text=True, timeout=timeout, cwd=str(_workdir(e)), env=_env())
        doc = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        doc = None
    items = doc.get("capabilities") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        return {"error": "az export nem olvasható"}
    kept = [v for v in (_valid(c) for c in items) if v]
    return {"capabilities": kept, "dropped": len(items) - len(kept)}


def collect(host: str | None = None, timeout: int = 10) -> dict:
    host = host or local_host()
    out = {}
    DIR.mkdir(parents=True, exist_ok=True)
    for e in agents_for_host(host or ""):
        if e.get("status") not in (None, "active", "dormant"):
            continue
        res = dict(_export(e, timeout), agent=e["agent"], at=time.time())
        tmp = DIR / (e["agent"] + ".json.tmp")
        tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        tmp.replace(DIR / (e["agent"] + ".json"))
        out[e["agent"]] = res
    return out


def collect_if_due(now: float | None = None) -> bool:
    snaps = list(DIR.glob("*.json")) if DIR.is_dir() else []
    if snaps and (now or time.time()) - max(p.stat().st_mtime for p in snaps) < DAY:
        return False
    collect()
    return True


def _tokens(text: str) -> list[str]:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= 3]


def _hit(q: str, c: str) -> bool:
    short, long_ = sorted((q, c), key=len)
    return q == c or (len(short) >= 4 and long_.startswith(short))


def find(as_agent: str, query: str, limit: int = 5) -> dict:
    host = local_host()
    me = get_agent(as_agent)
    if me is None or host is None or me.get("host") not in (None, host):
        raise Refused("a kérdező nem ennek a boxnak az ágense: %s" % as_agent)
    q = _tokens(query)
    scored = []
    for e in agents_for_host(host, load_agents()):
        if e["agent"] == as_agent:
            continue
        try:
            snap = json.loads((DIR / (e["agent"] + ".json")).read_text())
        except (OSError, ValueError):
            continue
        for c in snap.get("capabilities") or [] if isinstance(snap, dict) else []:
            v = _valid(c)  # read back as untrusted too
            words = _tokens(" ".join(v["intent"]) + " " + v["id"].replace(".", " ")) if v else []
            score = sum(1 for t in q if any(_hit(t, w) for w in words))
            if v and score and v["provenance"] != "suite":  # the suite is in every finder already
                scored.append((score, dict(v, agent=e["agent"])))
    scored.sort(key=lambda s: -s[0])
    return {"schema": 1, "results": [r for _, r in scored[:limit]]}
