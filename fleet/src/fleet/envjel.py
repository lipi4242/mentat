"""Lát-e a futó ágens felügyelet nélküli jelet a környezetében (nemakad, CISO 10-24).

A nem-akadó jóváhagyás hookja (security/eszkozok/identitas/nemakad.py) a `FLEET_AGENT`,
`THUFIR_AGENT` vagy `MENTAT_HEADLESS` változóból tudja, hogy a boxon senki nem hagyhat jóvá.
A sablonos unit exportálja, egy kézzel írt unit (`unit_source: file`) nem feltétlenül:
ott egy engedélykérés örökre megállíthatja az ágenst. Ezt mutatja a doctor.

Csak a változók NEVÉT olvassuk a /proc/<pid>/environ-ból, az értéket soha (token lehet benne).
"""
from __future__ import annotations
from pathlib import Path

JELEK = ("FLEET_AGENT", "THUFIR_AGENT", "MENTAT_HEADLESS")


def env_names(raw: bytes) -> set[str]:
    """Pure: a NUL-elválasztott environ-ból csak a nevek (nem üres értékűek)."""
    out = set()
    for item in raw.split(b"\0"):
        name, eq, value = item.partition(b"=")
        if eq and value:
            out.add(name.decode("utf-8", "replace"))
    return out


def verdict(names: set[str] | None) -> tuple[str | None, str | None]:
    """Pure: (probléma, nem-mérhető) — legfeljebb az egyik nem None."""
    if names is None:
        return None, "a claude-processz környezete nem olvasható (/proc/<pid>/environ)"
    if names & set(JELEK):
        return None, None
    return ("a claude-processz környezetében nincs FLEET_AGENT/THUFIR_AGENT/MENTAT_HEADLESS — "
            "a nem-akadó hook kérdező módban marad, egy engedélykérés örökre megállíthatja "
            "(kézi unit? tedd az env-fájlba: MENTAT_HEADLESS=1)"), None


def read_names(pid: int | None, proc: Path = Path("/proc")) -> set[str] | None:
    if not pid:
        return None
    try:
        return env_names((proc / str(int(pid)) / "environ").read_bytes())
    except (OSError, ValueError):
        return None


def check(pid: int | None, proc: Path = Path("/proc")) -> tuple[str | None, str | None]:
    return verdict(read_names(pid, proc))
