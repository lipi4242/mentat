"""`fleet map move-check <régi> <új> [--dups lista.md]`: 0 tiszta · 1 van lelet · 2 olvashatatlan fájl."""
from __future__ import annotations
import json
from pathlib import Path

from fleet import move_check, move_check_dups


def cmd_move_check(a) -> int:
    try:
        old = Path(a.old).read_text(encoding="utf-8")
        new = Path(a.new).read_text(encoding="utf-8")
        dups_text = Path(a.dups).read_text(encoding="utf-8") if a.dups else ""
    except OSError as e:
        print(json.dumps({"schema": 1, "error": str(e)}) if a.json else f"fleet: {e}")
        return 2
    covered, findings = move_check_dups.parse(dups_text, Path(a.dups).parent if a.dups else Path("."), new)
    findings += move_check.check(old, new, covered)
    if a.json:
        print(json.dumps({"schema": 1, "ok": not findings, "findings": [f.as_dict() for f in findings]}, ensure_ascii=False, indent=1))
    else:
        for f in findings:
            print(f"HIBA [{f.code}] {f.message}")
        print("fleet map move-check: tiszta mozgatás" if not findings else f"fleet map move-check: {len(findings)} lelet")
    return 1 if findings else 0
