"""`fleet registry set <ágens> <kulcs>=<érték> --owner-text "<a tulajdonos szó szerinti igene>"`

A registry egy mezőjének átírása a tulajdonos kifejezett igenjével (naplózott önbevallás, nem
hitelesítés; a híd által aláírt igen v2), kézi JSON-szerkesztés helyett
(H5-3, 2026-10-29: a fejlesztő ágens pythonnal írta át a `dormant`-ot és a tick-periódust).
Csak a felsorolt kulcsok írhatók, ellenőrzött értékkel. Ha a registry git-repó, a változás egy
commit, amelynek üzenetében ott a tulajdonos igene; ha nem, a `registry-nyugtak.jsonl`-be kerül.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time

from fleet import registry_dir
from fleet import registry as reg
from fleet import tick_period

KEYS = {
    "status": lambda v: v if v in reg.AGENT_STATUSES else None,
    "tick_period_s": lambda v: int(v) if v.isdigit() and _calendar_ok(int(v)) else None,
}


def _calendar_ok(period: int) -> bool:
    try:
        tick_period.calendar(period)
        return True
    except ValueError:
        return False


NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: ha a registry-repóban nincs git-identitás, a commit ezzel megy (nem a tulajdonos nevében)
GIT_ID = ["-c", "user.name=fleet registry set", "-c", "user.email=fleet@localhost"]


def apply(agent: str, assignment: str, owner_text: str, rdir=None) -> str:
    """Visszaad: egysoros jelentés. ValueError, ha nem írható."""
    if not NAME.match(agent or ""):
        raise ValueError(f"érvénytelen ágensnév: {agent!r} (kisbetű, szám, kötőjel)")
    if not owner_text.strip():
        raise ValueError("--owner-text: a tulajdonos szó szerinti igene kell (a kifejezett kérdésedre)")
    key, sep, raw = assignment.partition("=")
    if not sep or key not in KEYS:
        raise ValueError(f"írható kulcsok: {', '.join(KEYS)} (alak: kulcs=érték)")
    val = KEYS[key](raw.strip())
    if val is None:
        raise ValueError(f"{key}: érvénytelen érték: {raw!r}")
    d = rdir or registry_dir()
    path = d / "agents.json"
    agents = reg.load_json(path, None)
    if not isinstance(agents, list):
        raise ValueError(f"{path}: nem olvasható lista")
    hit = [a for a in agents if isinstance(a, dict) and a.get("agent") == agent]
    if not hit:
        raise ValueError(f"{agent}: nincs a registryben")
    old = hit[0].get(key)
    hit[0][key] = val
    reg.save_json(path, agents)
    msg = f"registry: {agent} {key}={val} (előtte: {old})\n\nA tulajdonos igene: {owner_text.strip()}"
    if (d / ".git").exists():
        ident = [] if subprocess.run(["git", "-C", str(d), "config", "user.email"], capture_output=True).stdout.strip() \
            else GIT_ID
        r = subprocess.run(["git", "-C", str(d), *ident, "commit", "-q", "-m", msg, "--", "agents.json"],
                           capture_output=True, text=True)
        if r.returncode:
            raise ValueError(f"a commit nem sikerült: {(r.stderr or r.stdout).strip()[-200:]}")
    else:
        with open(d / "registry-nyugtak.jsonl", "a") as f:
            f.write(json.dumps({"t": int(time.time()), "agent": agent, key: val, "elotte": old,
                                "owner_text": owner_text.strip()}, ensure_ascii=False) + "\n")
    out = f"{agent}: {key} {old} → {val}"
    if key == "tick_period_s":
        try:
            out += "\n" + tick_period.apply(agent, val)
        except (ValueError, OSError) as e:
            raise ValueError(f"{out} (a registry már átírva), de az ÜTEM NEM állt át: {e}") from None
    return out


def cmd(a) -> int:
    try:
        print(apply(a.agent, a.assignment, a.owner_text))
    except ValueError as e:
        print(f"registry set: {e}", file=sys.stderr)
        return 2
    return 0


def add_parser(sub) -> None:
    r = sub.add_parser("registry", help="a registry egy mezője a tulajdonos igenjével (kézi JSON-írás helyett)")
    rs = r.add_subparsers(dest="sub", required=True)
    x = rs.add_parser("set", help="status=active|dormant, tick_period_s=<900|1800|3600|…> (a tick-timer ütemét is átírja)")
    x.add_argument("agent", metavar="ágens")
    x.add_argument("assignment", metavar="kulcs=érték")
    x.add_argument("--owner-text", required=True, help="a tulajdonos szó szerinti igene a kifejezett kérdésedre — "
                                                       "naplózott önbevallás, nem hitelesítés (a commitban látszik)")
    x.set_defaults(fn=cmd)
