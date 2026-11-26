"""A duplikátum-lista (`--dups`): „törölve, mert duplikált: <sor> → itt maradt meg: <hely>” sorok.
A hely: `<fájl>:<sor>` (a fájl az adott sorban tényleg ez a sor), vagy `#<cím>` / `szakasz: <cím>` (az új fájl címsora)."""
from __future__ import annotations
import re
from collections import Counter
from pathlib import Path

from fleet import move_check
from fleet.fleet_map import Finding

_ROW = re.compile(r"^törölve, mert duplikált:\s*(.+?)\s*→\s*itt maradt meg:\s*(.+)$")
_FILE_LINE = re.compile(r"^(.+):(\d+)$")


def _place_ok(place: str, line: str, base: Path, new_text: str) -> bool:
    m = _FILE_LINE.match(place)
    if m:
        p = Path(m.group(1))
        p = p if p.is_absolute() else base / p
        try:
            rows = dict(move_check.lines(p.read_text(encoding="utf-8")))
        except OSError:
            return False
        return rows.get(int(m.group(2))) == line
    title = re.sub(r"^(?:szakasz:\s*|#+\s*)", "", place).strip()
    return bool(title) and any(n.startswith("#") and n.lstrip("# ").strip() == title for _, n in move_check.lines(new_text))


def parse(text: str, base: Path, new_text: str) -> tuple[Counter, list[Finding]]:
    """(lefedett előfordulások sorok szerint — egy lista-sor egy előfordulás —, hibás sorok)."""
    covered, bad = Counter(), []
    for no, raw in enumerate(text.splitlines(), 1):
        n = move_check.normalize(raw)
        if not n:
            continue
        m = _ROW.match(n)
        if not m:
            bad.append(Finding("dups-bad-row", f"a duplikátum-lista {no}. sora nem a megadott alakú: {n}", subject=f"dups:{no}"))
            continue
        line, place = move_check.normalize(m.group(1)), m.group(2).strip()
        if _place_ok(place, line, base, new_text):
            covered[line] += 1
        else:
            bad.append(Finding("dups-bad-place", f"a duplikátum-lista {no}. sorában a hely nem igazolható: {place}", subject=f"dups:{no}"))
    return covered, bad
