"""Megbízható-e egy prompt-változás az automatikus restarthoz.

A drift-restart a változott promptot tölti be egy `--dangerously-skip-permissions`
alatt futó ágensbe. Ezért automatikusan csak az mehet, ami kiadott állapot:
  * minden változott munkakönyvtár-fájl git-követett, és egyezik a HEAD-del
    (a munkafa-bájtok, az index és a HEAD blobja ugyanaz), ÉS a HEAD az origin alapágának őse
    (`merge-base --is-ancestor`): a helyben commitolt, ki nem adott változás (az
    ágens maga is commitolhat) és a remote nélküli repó csak jelzés; a munkakönyvtáron kívüli változás
    (fiók konfig-gyökér, ős-könyvtár) és a nem követett fájl: csak jelzés
  * a figyelt settings.json-ok `hooks` kulcsa nem változott (hook = kódfuttatás
    minden eszközhívásnál): bármilyen hooks-változás csak jelzés
  * a figyelt settings.json-ok érvényes JSON-ok: a hibás settings mellett
    induló claude nem a várt beállításokkal futna — nincs restart, jelzés.
    A JSON-t abból a bájtsorból parse-oljuk, amit a biztonságos olvasás beolvasott
    (prompt_safe_read.read_bytes), nem olvassuk újra (TOCTOU)
A git-ellenőrzés (repó-konfig parancs nélkül): fleet.prompt_git.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

from fleet.prompt_git import git_problems, released  # noqa: F401  (a hívók innen érik el)
from fleet.prompt_safe_read import read_bytes

INVALID, UNTRUSTED = "invalid", "untrusted"
UNKNOWN_HOOKS = "ismeretlen"     # első kör, a settings az indulás után módosult


def _load(p: Path):
    """(objektum, hibás-e). Hiányzó fájl: (None, False)."""
    mark, data = read_bytes(p)
    if data is None:
        return None, mark is not None     # hiányzó fájl: nem hiba; jelölő (nem-fájl, nagy, olvashatatlan): hiba
    try:
        return json.loads(data.decode("utf-8")), False
    except ValueError:                    # UnicodeDecodeError is ValueError
        return None, True


def hooks_fp(p: Path) -> str | None:
    """A `hooks` kulcs ujjlenyomata; None, ha nincs fájl; 'hibas', ha nem JSON."""
    obj, bad = _load(p)
    if bad:
        return "hibas"
    if obj is None:
        return None
    hooks = obj.get("hooks") if isinstance(obj, dict) else None
    return hashlib.sha256(json.dumps(hooks, sort_keys=True).encode()).hexdigest()[:16]


def check(workdir: str, changed: list[str], base_hooks: dict, settings: list[Path],
          run=subprocess.run) -> tuple[str | None, str]:
    """(None | INVALID | UNTRUSTED, indok) a változott utakra."""
    bad = [str(p) for p in settings if _load(p)[1]]
    if bad:
        return INVALID, "hibás settings.json: " + ", ".join(Path(b).name for b in bad)
    hook_diff = [str(p) for p in settings
                 if base_hooks.get(str(p)) == UNKNOWN_HOOKS or base_hooks.get(str(p)) != hooks_fp(p)]
    if hook_diff:
        return UNTRUSTED, "hooks-változás a settings.json-ban (csak jelzés)"
    wd = Path(workdir).resolve()
    inside, outside = [], []
    for c in changed:
        try:
            inside.append(str(Path(c).resolve().relative_to(wd)))
        except (ValueError, OSError):
            outside.append(c)
    if outside:
        return UNTRUSTED, f"munkakönyvtáron kívüli változás ({len(outside)} fájl, csak jelzés)"
    probs = git_problems(wd, inside, run=run)
    if probs:
        return UNTRUSTED, f"nem kiadott (git-en kívüli vagy a HEAD-től eltérő) változás: {len(probs)} fájl"
    if inside and not released(wd, run=run):
        return UNTRUSTED, "a HEAD nincs az origin alapágán (helyi, ki nem adott commit; csak jelzés)"
    return None, ""
