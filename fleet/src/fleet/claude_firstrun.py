"""A Claude Code első indításának ablakai, előre elfogadva — hogy a unit alatt
futó claude ne álljon dialógusnál (elfogadási mérés 2026-10-15, 06-flotta).

Mérve a 2.1.x binárison (2026-10-16), a fiók könyvtára szerint
(`shared` = ~/.claude.json + ~/.claude/; nevesített = ~/.claude-<fiók>/ alatt
mindkettő, mert a CLAUDE_CONFIG_DIR mindkettőt odaviszi):

  .claude.json   hasCompletedOnboarding  — téma + bevezető ablak
                 theme                   — csak ha nincs (a meglévőt nem írjuk át)
                 remoteDialogSeen        — „Enable Remote Control?" ablak
                 projects[<workdir>].hasTrustDialogAccepted — workspace trust
                   (a claude a workdirtől a git-gyökérig felfelé keres)
  settings.json  skipDangerousModePermissionPrompt — a Bypass Permissions ablak
                   (a 2.1.x ezt a user settingsben keresi; a régi
                   bypassPermissionsModeAccepted-et maga migrálja ide)
                 hooks.SessionStart: bin/capture-session-id.sh — a --resume
                   alapja (a session.id rögzítése)

Idempotens: csak a hiányzó kulcsot írja, minden más kulcs megmarad. Hibás
JSON-t nem ír felül (az ember dönt). Írás: tmp + rename, a régi jogosultsággal
(új fájl: 0600). Tranzakción KÍVÜL fut: a .claude.json-t a box többi ágense
is írja, egy visszaállítás az ő közbenső írásukat vinné el.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path

from fleet import REPO_ROOT
from fleet.registry import SHARED_ACCOUNT

HOOK_SCRIPT = "capture-session-id.sh"


def config_paths(entry: dict, home: Path) -> tuple[Path, Path]:
    """(globális .claude.json, user settings.json) az ágens fiókjára."""
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    if acc == SHARED_ACCOUNT:
        return home / ".claude.json", home / ".claude" / "settings.json"
    d = home / f".claude-{acc}"
    return d / ".claude.json", d / "settings.json"


def workdir_key(entry: dict, home: Path) -> str:
    return str(Path(str(entry["workdir"]).replace("%h", str(home))).resolve())


def seed_global(doc: dict, workdir: str) -> list[str]:
    """Pure (a doc-ot helyben módosítja): a hiányzó kulcsok, a változások neve."""
    ch = []
    for k in ("hasCompletedOnboarding", "remoteDialogSeen"):
        if doc.get(k) is not True:
            doc[k] = True
            ch.append(k)
    if not doc.get("theme"):
        doc["theme"] = "dark"
        ch.append("theme")
    projects = doc.get("projects") if isinstance(doc.get("projects"), dict) else {}
    doc["projects"] = projects
    proj = projects.setdefault(workdir, {})
    if proj.get("hasTrustDialogAccepted") is not True:
        proj["hasTrustDialogAccepted"] = True
        ch.append(f"trust: {workdir}")
    return ch


def seed_settings(doc: dict, hook_cmd: str) -> list[str]:
    """Pure: Bypass-elfogadás + a session-id hook: pontosan egy, a mi checkoutunk szkriptje
    (egy máshonnan bejegyzett capture-session-id.sh-t a sajátunkra cserélünk)."""
    ch = []
    if doc.get("skipDangerousModePermissionPrompt") is not True:
        doc["skipDangerousModePermissionPrompt"] = True
        ch.append("skipDangerousModePermissionPrompt")
    hooks = doc.get("hooks") if isinstance(doc.get("hooks"), dict) else {}
    doc["hooks"] = hooks
    groups = hooks.get("SessionStart") if isinstance(hooks.get("SessionStart"), list) else []
    hooks["SessionStart"] = groups
    have = [h for g in groups if isinstance(g, dict) for h in g.get("hooks") or []
            if isinstance(h, dict) and HOOK_SCRIPT in str(h.get("command", ""))]
    if not have:
        groups.append({"hooks": [{"type": "command", "command": hook_cmd}]})
        ch.append(f"SessionStart hook: {hook_cmd}")
        return ch
    # Egy hook marad, és az a miénk: egy másik checkoutból bejegyzett (régi) hook nem
    # feltétlenül ismeri a FLEET_AGENT-et (L23), ezért a sajátunkra cseréljük.
    for i, h in enumerate(have):
        if i == 0 and h.get("command") != hook_cmd:
            ch.append(f"SessionStart hook: {h.get('command')} -> {hook_cmd}")
            h["command"] = hook_cmd
        elif i > 0:
            for g in groups:
                if isinstance(g, dict) and h in (g.get("hooks") or []):
                    g["hooks"].remove(h)
            ch.append(f"SessionStart hook: dupla törölve ({h.get('command')})")
    hooks["SessionStart"] = [g for g in groups if not (isinstance(g, dict) and g.get("hooks") == [])]
    return ch


def _load(p: Path) -> dict | None:
    """A fájl tartalma; {} ha nincs; None ha nem érvényes JSON-objektum."""
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text() or "{}")
    except (OSError, json.JSONDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = (p.stat().st_mode & 0o777) if p.exists() else 0o600
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def apply(entry: dict, *, home: Path, check: bool = False,
          hook_cmd: str | None = None) -> dict:
    """{"changes": [...], "problems": [...]} — `check` esetén nem ír."""
    hook_cmd = hook_cmd or str(REPO_ROOT / "bin" / HOOK_SCRIPT)
    gpath, spath = config_paths(entry, home)
    out = {"changes": [], "problems": []}
    for path, seed, arg in ((gpath, seed_global, workdir_key(entry, home)),
                            (spath, seed_settings, hook_cmd)):
        doc = _load(path)
        if doc is None:
            out["problems"].append(f"{path} nem érvényes JSON — nem írom felül; javítsd, aztán futtasd újra")
            continue
        ch = seed(doc, arg)
        if ch and not check:
            _write(path, doc)
        out["changes"] += [f"{path.name}: {c}" for c in ch]
    return out
