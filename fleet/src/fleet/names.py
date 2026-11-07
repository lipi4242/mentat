"""Névszabályok. Egy ágensnek egy flottaneve van; minden más név ebből
származik vagy a registryben van kimondva.

Amit NEM tudunk: a natív SendMessage-cím (munkakönyvtár + hash) generált,
minden indulásnál más — ezért nem tároljuk, hanem mérjük (`roster`), és a
`from=` cím a horgony egy beérkezett üzenetnél. A `from=` állítás, nem
hitelesítés.
"""
from __future__ import annotations
import re

#: kisbetű, szám, kötőjel; betűvel kezdődik; max 40. Ez a tmux session,
#: a unit és a --remote-control név közös metszete.
_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


def is_valid_agent_name(name: str) -> bool:
    return bool(name) and bool(_SLUG.match(name))


def name_findings(entry: dict) -> list[str]:
    """Pure: a bejegyzés névproblémái, emberi mondatokban."""
    out = []
    a = entry.get("agent", "")
    if not is_valid_agent_name(a):
        out.append(f"agent név nem slug: {a!r}")
    for key in ("session", "rc_name"):
        v = entry.get(key)
        if v and not is_valid_agent_name(v):
            out.append(f"{key} nem slug: {v!r}")
    unit = entry.get("unit", "")
    if unit and not unit.endswith(".service"):
        out.append(f"unit nem .service: {unit!r}")
    return out
