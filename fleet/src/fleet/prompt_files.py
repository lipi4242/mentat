"""Az ágens betöltött promptja fájlonként, tartalom-hash-sel.

Ami egy claude-processz indulásakor a kontextusba kerül, és frissítéskor
változhat: a CLAUDE.md (a munkakönyvtár és az ősei, a fiók-gyökér), a
CLAUDE.local.md, az AGENTS.md, ezek @include-lánca, a `.claude/rules/**`,
`.claude/commands/**`, `.claude/skills/**`, `.claude/agents/**` és a
`.claude/settings.json` — a munkakönyvtárban és a fiók konfig-gyökerében.
Az olvasás őrzött (prompt_safe_read): nem-fájl, óriásfájl, symlink a fában és
a gyökereken kívülre mutató @include nem akaszthatja meg és nem tágíthatja a kört.

Csak a tartalom számít (sha256), az mtime nem: egy `git checkout`, ami
ugyanazt a bájtsort írja vissza, nem változás. A hiányzó fájl is állapot
(`None`): egy törölt szabályfájl ugyanúgy változás, mint egy átírt.
"""
from __future__ import annotations
import re
import time
from pathlib import Path

from fleet.prompt_safe_read import confined, digest, walk
from fleet.registry import SHARED_ACCOUNT

TOP_FILES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
TREES = ("rules", "commands", "skills", "agents")
#: a `.claude/settings.local.json` NINCS benne: futásidőben az ágens maga írja
#: (engedélyek), és minden ilyen írás restartot váltana ki
SETTINGS = ("settings.json",)
MAX_DEPTH = 5          # az @include-lánc mélysége (a Claude Code is korlátoz)
MAX_FILES = 2000       # egy elszabadult skill-fa se tegye lassúvá a 5 perces kört
TIME_BUDGET_S = 20.0   # ágensenként; túllépve a mérés ebben a körben elmarad (None)
_INCLUDE = re.compile(r"(?:^|\s)@((?:~/|\.{1,2}/|/)?[\w.\-][\w.\-/]*)")


def config_root(entry: dict, home: Path) -> Path:
    """A fiók konfig-gyökere — ugyanaz a szabály, mint a unit CLAUDE_CONFIG_DIR-je."""
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    return home / ".claude" if acc == SHARED_ACCOUNT else home / f".claude-{acc}"


def includes(text: str, base: Path, home: Path) -> list[Path]:
    """Pure: a szöveg @hivatkozásai feloldva; kódblokkon belül nem számít."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        for ref in _INCLUDE.findall(line):
            if "/" not in ref and "." not in ref:
                continue          # @név (említés), nem fájl
            ref = ref.rstrip(".,;:)")
            p = home / ref[2:] if ref.startswith("~/") else Path(ref) if ref.startswith("/") else base / ref
            out.append(p)
    return out


def settings_paths(entry: dict, home: Path) -> list[Path]:
    """A figyelt settings.json-ok (a hooks- és JSON-őr ezeket nézi)."""
    return [Path(entry.get("workdir") or ".") / ".claude" / s for s in SETTINGS] + [config_root(entry, home) / "settings.json"]


def roots(entry: dict, home: Path) -> list[Path]:
    """A kiinduló fájlok (létezőek és nem létezőek is: a megjelenés is változás)."""
    wd = Path(entry.get("workdir") or ".")
    cfg = config_root(entry, home)
    out = [wd / f for f in TOP_FILES]
    for anc in wd.parents:
        if anc == anc.parent:
            break
        out += [anc / "CLAUDE.md", anc / "CLAUDE.local.md"]
    out += settings_paths(entry, home) + [cfg / "CLAUDE.md"]
    for base in (wd / ".claude", cfg):
        for t in TREES:
            out += walk(base / t, MAX_FILES)
    return out


def snapshot(entry: dict, home: Path | None = None, clock=time.monotonic) -> dict[str, str | None] | None:
    """út → sha256 (vagy jelölő, vagy None, ha nincs). Az @include-lánc bejárva,
    ciklus nélkül, csak a munkakönyvtáron és a fiók konfig-gyökerén belül.
    None: az időkeret elfogyott — ebben a körben nincs mérés (nem hamis drift)."""
    home = home or Path.home()
    bases = [Path(entry.get("workdir") or "."), config_root(entry, home)]
    seen: dict[str, str | None] = {}
    queue = [(p, 0) for p in roots(entry, home)]
    deadline = clock() + TIME_BUDGET_S
    while queue and len(seen) < MAX_FILES:
        if clock() > deadline:
            return None
        p, depth = queue.pop(0)
        key = str(p)
        if key in seen:
            continue
        h, text = digest(p)
        seen[key] = h
        if text is None or depth >= MAX_DEPTH:
            continue
        for q in includes(text, p.parent, home):
            r = confined(q, bases)
            if r is not None:
                queue.append((r, depth + 1))
    return seen


def newer_than(paths, t: float, slack_s: float = 2.0) -> list[str]:
    """A létező utak, amelyek mtime-ja `t` UTÁNI (az első alapvonal tartaléka)."""
    out = []
    for k in paths:
        try:
            if Path(k).stat().st_mtime > t + slack_s:
                out.append(k)
        except OSError:
            continue
    return sorted(out)


def changed(old: dict, new: dict) -> list[str]:
    """Pure: a tartalmilag eltérő utak (új, törölt, átírt), rendezve."""
    return sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
