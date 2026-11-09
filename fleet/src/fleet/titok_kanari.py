"""11-07: a titok-kapu bevezetése — essentials-próba a jelölt kódon, aztán kanári.

    rollout(home, sha, stamp, agents, force) -> [jegyzet]

1. a jelölt kód (~/.mentat/bin/titok-kapu/<sha>/) az ágensek alapfunkcióin (essentials.py): ha
   egy ágens küldése/todo-ja/git-je tiltva lenne, vagy hidas ágens unitjából hiányzik a token,
   NEM telepít (a `--force` telepít, de a listát hangosan kiírja);
2. kanári: a bejegyzés előbb CSAK az első Claude-gyökérbe kerül, és a próba a ténylegesen beírt
   parancssorral fut újra; piros → a gyökér visszaáll a mentésből, a `current` az előző kódra,
   a többi gyökér érintetlen;
3. csak ezután a többi gyökér.
A Claude Code a settings-hookokat azonnal újraolvassa: ami beíródik, az a futó sessionökben is él.
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path

from fleet import essentials as E


class Refused(RuntimeError):
    pass


def _registered(root: Path) -> str | None:
    from fleet import titok_telepit as T
    try:
        pre = json.loads((root / "settings.json").read_text()).get("hooks", {}).get("PreToolUse") or []
    except (OSError, ValueError, AttributeError):
        return None
    own = [h for e in pre if T._ours(e) for h in e["hooks"]]
    return own[0].get("command") if own else None


def _rollback(root: Path, stamp: str) -> None:
    from fleet import titok_telepit as T
    p, bak = root / "settings.json", root / f"settings.json.bak-titok-{stamp}"
    if bak.exists():
        shutil.copy2(bak, p)
        return
    if not p.exists():
        return
    data = json.loads(p.read_text())
    pre = data.get("hooks", {}).get("PreToolUse") or []
    data["hooks"]["PreToolUse"] = [e for e in pre if not T._ours(e)]
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _gate_or_raise(res: dict, force: bool, what: str, notes: list[str]) -> None:
    if not E.blocking(res):
        return
    text = E.format_probe(res)
    if not force:
        raise Refused(f"titok-kapu: NEM telepítem ({what}) — ágens-alapfunkció sérülne:\n{text}\n"
                      "Javítsd a fenti sorok szerint, vagy `fleet secrets hook install --force` (a lista ott is kiíródik).")
    notes.append(f"!!! --force: a titok-kapu ezekkel a HIBÁKKAL települ ({what}):\n{text}")


def rollout(home: Path, sha: str, stamp: str, agents: list[dict], force: bool = False,
            dry_run: bool = False) -> list[str]:
    from fleet import titok_telepit as T
    notes: list[str] = []
    res = E.probe(agents, home, code=T.code_dir(home) / sha)
    if dry_run:  # a jelölt kód a <sha>/ alatt él, de semmi nem mutat rá: nincs viselkedésváltozás
        return [E.format_probe(res), f"--dry-run: a `current` és a settings.json érintetlen; élesben ezek "
                f"kapnák a hookot: {', '.join(str(r / 'settings.json') for r in T.roots(home))}"]
    _gate_or_raise(res, force, "jelölt kód", notes)
    cur = T.code_dir(home) / "current"
    prev = os.readlink(cur) if cur.is_symlink() else None
    T._switch(home, sha)  # a meglévő bejegyzések a `current`-re mutatnak: a jelölt kódot az 1. lépés már próbálta
    rs, cmd = T.roots(home), None
    while rs and cmd is None:  # kanári: az első gyökér, ahova a bejegyzés valóban beírható
        canary, rs = rs[0], rs[1:]
        n = T._register(canary, home, stamp)
        if n:
            notes.append(n + " (kanári)")
        cmd = _registered(canary)
    if cmd is None:
        raise Refused("titok-kapu: egyik Claude-gyökérbe sem írható be a bejegyzés — leállok")
    try:
        _gate_or_raise(E.probe(agents, home, command=cmd), force, f"kanári: {canary.name}", notes)
    except Refused:
        if n:
            _rollback(canary, stamp)
        if prev:
            T._switch(home, prev)
        raise
    rest = rs
    notes += [m for m in (T._register(r, home, stamp) for r in rest) if m]
    notes.append(f"essentials: {len(agents)} ágens próbálva a jelölt kódon és a kanárin")
    from fleet import kanari  # 11-07: a lenyomat rögzítése — a doctor ebből látja, ha utána más írt ide
    kanari.record(home, T.roots(home), "titok-kapu: hook install")
    return notes
