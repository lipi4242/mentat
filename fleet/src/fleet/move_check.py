"""Mozgatás-ellenőrző: bizonyítja, hogy egy ágens-fájl átrendezése csak mozgatás volt.
Tiszta függvények, semmit nem írnak. A `mentat:managed` blokkok tartalmát mindkét oldalon kihagyja.

Szabály (számláló alapú): ha egy sor N-szer volt a régiben és M-szer van az újban, a hiányzó N-M
előfordulásnak a duplikátum-listán kell lennie (egy lista-sor egy előfordulást fed le);
az újban új sor csak címsor vagy managed-jelölő lehet. Minden más lelet (átfogalmazás = külön emberi PR).
"""
from __future__ import annotations
import re
from collections import Counter

from fleet.fleet_map import Finding

_LIST = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_START = re.compile(r"<!--\s*mentat:managed:start\s+(\S+)\s*-->")
_END = re.compile(r"<!--\s*mentat:managed:end\s+(\S+)\s*-->")


def normalize(line: str) -> str:
    """Whitespace összevonva, lista-jel és sorvégi szóköz lecsupaszítva."""
    return _LIST.sub("", " ".join(line.split()))


def lines(text: str) -> list[tuple[int, str]]:
    """(eredeti sorszám, normalizált sor); üres sorok és managed blokkok (jelölőkkel) kihagyva."""
    out, open_id = [], None
    for no, raw in enumerate(text.splitlines(), 1):
        if open_id is None:
            m = _START.search(raw)
            if m:
                open_id = m.group(1)
                continue
            n = normalize(raw)
            if n:
                out.append((no, n))
        else:
            m = _END.search(raw)
            if m and m.group(1) == open_id:
                open_id = None
    return out


def check(old: str, new: str, dups: Counter | set | None = None) -> list[Finding]:
    left = Counter(dups or ())
    old_l, new_l = lines(old), lines(new)
    have, in_old = Counter(n for _, n in new_l), {n for _, n in old_l}
    nos: dict[str, list[int]] = {}
    for no, n in old_l:
        nos.setdefault(n, []).append(no)
    out = []
    for n, where in nos.items():
        missing = max(0, len(where) - have[n])
        unresolved = max(0, missing - left[n])
        for no in where[len(where) - unresolved:]:  # a hiányzók: a későbbi előfordulások
            out.append(Finding("line-lost", f"elveszett sor (régi {no}. sor): {n}", subject=f"old:{no}"))
    for no, n in new_l:
        if n not in in_old and not n.startswith("#"):
            out.append(Finding("text-new", f"új szöveg (új {no}. sor): {n} — átfogalmazás, külön emberi PR kell", subject=f"new:{no}"))
    return sorted(out, key=lambda f: (f.code != "line-lost", int(f.subject.split(":")[1])))
