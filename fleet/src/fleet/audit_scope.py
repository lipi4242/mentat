"""Audit: a gyökér (CLAUDE.md, .claude/rules/) és a kóbor szülő-fájlok. Csak olvas.
A Claude Code felfelé haladva tölt be: a szülő CLAUDE.md és .claude/rules/ minden almappára hat."""
from __future__ import annotations
from pathlib import Path

from fleet import fleet_root


def check_root(root: Path, fmap: dict, mk) -> list:
    out = []
    f = root / "CLAUDE.md"
    text = f.read_text(encoding="utf-8") if f.is_file() else None
    if text is None or fleet_root.parse_hash(text) is None:
        out.append(mk("root-missing", f"nincs generált fleet-root blokk a gyökér CLAUDE.md-ben ({f})", subject=str(f)))
    else:
        try:
            want = fleet_root.render(fmap)
        except fleet_root.RootError as e:
            return out + [mk("root-drift", f"a gyökérfájl nem generálható: {e}", subject=str(f))]
        if text != want:
            same = fleet_root.parse_hash(text) == fleet_root.source_hash(fmap)
            out.append(mk("root-foreign-content" if same else "root-drift",
                          f"a gyökér CLAUDE.md {'nem csak a generált blokkot tartalmazza' if same else 'eltér a térképtől'} ({f})",
                          subject=str(f)))
    rules = root / ".claude" / "rules"
    if rules.is_dir():
        for p in sorted(q for q in rules.rglob("*") if q.is_file()):
            out.append(mk("root-rules-foreign", f"nem generált fájl a gyökér .claude/rules/ alatt: {p}", subject=str(p)))
    return out


def check_parents(repo: Path, home: Path, skip: set[Path], mk) -> list:
    """Kóbor CLAUDE.md / .claude/rules a repó szülőmappáiban, a HOME-ig (azt is beleértve)."""
    out = []
    home, cur = home.resolve(), repo.resolve().parent
    while True:
        if cur not in skip:
            if (cur / "CLAUDE.md").is_file():
                out.append(mk("stray-parent-claude", f"kóbor CLAUDE.md a szülőmappában: {cur / 'CLAUDE.md'}", subject=str(cur / "CLAUDE.md")))
            if (cur / ".claude" / "rules").exists():
                out.append(mk("stray-parent-rules", f"kóbor .claude/rules a szülőmappában: {cur / '.claude' / 'rules'}", subject=str(cur / ".claude" / "rules")))
        if cur == home or cur == cur.parent:
            return out
        cur = cur.parent
