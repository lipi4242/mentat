"""Read/write + pure transforms for the deploy registries. No secrets.

A registry azt mondja meg, HOL és HOGYAN fut egy ágens. Amit nem mond ki,
azt a `normalize` tölti ki determinisztikusan — így egy régi bejegyzés a
jelentését megtartja, és minden fogyasztó ugyanazt az alakot látja.
"""
from __future__ import annotations
import json, os, socket
from pathlib import Path

from fleet import CONFIG_DIR, registry_dir


def load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


#: The registry's agent lifecycle states. Absent status means "active" —
#: every pre-existing entry keeps its meaning without a migration.
AGENT_STATUSES = ("active", "dormant")

#: A közös ~/.claude credential explicit neve. A `null` fiók NEM "nincs
#: fiók", hanem "a közös" — a Codex F0-review 2. pontja: néma visszaesés
#: helyett kimondott döntés.
SHARED_ACCOUNT = "shared"


def is_dormant(entry: dict) -> bool:
    """Pure: is this agent deliberately at rest (not running on its box)?

    Dormant is DESIRED state, unlike a maintenance lock: no TTL, survives
    restarts, and supervision (reconcile/liveness) must never resurrect the
    agent.
    """
    return entry.get("status") == "dormant"


def normalize(entry: dict) -> dict:
    """Pure: a bejegyzés teljes alakja, minden alapérték kitöltve.

    Nem módosítja a bemenetet. A szabályok:
      * `status`   hiányzik → "active"
      * `claude_account` hiányzik/null → "shared" (a Claude-credential; az
                    `account` mező a régi jelentését tartja: accounts.json-hivatkozás)
      * `unit`     hiányzik → "<agent>.service"
      * `session`  hiányzik → agent
      * `rc_name`  hiányzik → agent  (a --remote-control neve; a régi ágensek
                    kézzel kaphattak rövidebbet, ezért mező, nem levezetés)
      * `env_file` hiányzik → "telegram.env" (a ~/.config/<agent>/ alatt)
      * `unit_source` hiányzik → "template"
      * `supervision` hiányzik → "fleet" (a másik érték: "none" — pl. egy
                    Macen futó, időszakosan elérhető tag)
      * `proactive` hiányzik → False
    """
    e = dict(entry)
    name = e.get("agent", "")
    e.setdefault("status", "active")
    if not e.get("claude_account"):
        e["claude_account"] = SHARED_ACCOUNT
    e.setdefault("unit", f"{name}.service")
    e.setdefault("session", name)
    e.setdefault("rc_name", name)
    e.setdefault("env_file", "telegram.env")
    e.setdefault("unit_source", "template")
    e.setdefault("supervision", "fleet")
    e.setdefault("proactive", False)
    return e


def env_files(entry: dict) -> list[str]:
    """Pure: a unit env-fájljai (fájlnevek a ~/.config/<agent>/ alatt), betöltési sorrendben.

    `env_files: [...]` (új) vagy az `env_file` (régi, egy fájl). 11-07: hidas ágensnél a híd
    env-fájlja (`bridge.env_file`, alap telegram.env) MINDIG benne van, ELSŐként — így a send.mjs
    tokenje a unit env-jéből jön, az ágens saját fájlja pedig felülírhatja a közös kulcsokat."""
    own = [f for f in (entry.get("env_files") or [entry.get("env_file") or "telegram.env"]) if f]
    b = entry.get("bridge") or {}
    first = [b.get("env_file") or "telegram.env"] if b.get("unit") else []
    return list(dict.fromkeys(first + own))


def load_boxes(path: Path | None = None) -> list[dict]:
    """A boxes.json gépei. Két alakot fogad el: `{"boxes": [...]}` és a csupasz listát (régi,
    kézzel írt registry; H5 2026-10-29: a roster/doctor/ask ezen összeomlott)."""
    doc = load_json(Path(path) if path else registry_dir() / "boxes.json", {})
    boxes = doc.get("boxes", []) if isinstance(doc, dict) else doc
    return [b for b in boxes if isinstance(b, dict)] if isinstance(boxes, list) else []


def load_agents(path: Path | None = None) -> list[dict]:
    """Minden bejegyzés normalizálva. Hiányzó/sérült fájl → üres lista
    (a felügyelet ilyenkor nem csinál semmit, nem omlik össze). Ha a registry
    maga nincs beállítva, `RegistryNotConfigured` — az nem üres flotta."""
    p = Path(path) if path else registry_dir() / "agents.json"
    return [normalize(a) for a in load_json(p, []) if isinstance(a, dict) and a.get("agent")]


def get_agent(name: str, agents: list[dict] | None = None) -> dict | None:
    for a in (agents if agents is not None else load_agents()):
        if a["agent"] == name:
            return a
    return None


def local_host(boxes: list[dict] | None = None) -> str | None:
    """Ez a gép melyik box a registryben.

    Sorrend: FLEET_HOST env → ~/.config/fleet/host fájl → boxes.json
    `hostname` mezője a gép hostnevére → None. A None azt jelenti: nem
    tudjuk — a reconcile ilyenkor csak megfigyel (ne essünk vissza némán
    egy alapértelmezett boxra).
    """
    env = os.environ.get("FLEET_HOST")
    if env:
        return env
    try:
        f = (Path(os.path.expanduser("~")) / ".config" / "fleet" / "host").read_text().strip()
        if f:
            return f
    except OSError:
        pass
    hn = socket.gethostname()
    for b in (boxes if boxes is not None else load_boxes()):
        if b.get("hostname") == hn or b.get("key") == hn:
            return b["key"]
    return None


def host_matches(entry: dict, host: str) -> bool:
    """Ez a gép őrzi-e ezt az ágenst. A None host "mindenhol" (kompatibilis)."""
    h = entry.get("host")
    return h in (None, host)


def agents_for_host(host: str, agents: list[dict] | None = None) -> list[dict]:
    return [a for a in (agents if agents is not None else load_agents()) if host_matches(a, host)]


def add_person(reg: dict, name: str, user_id: str, notes: str = "") -> dict:
    reg.setdefault("people", [])
    for p in reg["people"]:
        if p["telegram_user_id"] == user_id:
            p["name"], p["notes"] = name, notes
            return reg
    reg["people"].append({"name": name, "telegram_user_id": user_id, "notes": notes})
    return reg


def add_group(reg: dict, name: str, group_id: str, members: list,
              require_mention: bool = True) -> dict:
    reg.setdefault("groups", [])
    for g in reg["groups"]:
        if g["group_id"] == group_id:
            g.update(name=name, members=members, require_mention=require_mention)
            return reg
    reg["groups"].append({"name": name, "group_id": group_id,
                          "members": members, "require_mention": require_mention})
    return reg


def upsert_agent(agents: list, entry: dict) -> list:
    for i, a in enumerate(agents):
        if a["agent"] == entry["agent"]:
            agents[i] = entry
            return agents
    agents.append(entry)
    return agents
