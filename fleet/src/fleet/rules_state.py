"""A repó `.claude/rules/fleet.md` fájlja a telepített sablonhoz mérve. Csak olvas.
A „régi” a repóban lévő fájl hash-e, az „új” a telepített (vagy megadott) sablonból renderelt szövegé."""
from __future__ import annotations
import re
from pathlib import Path

from fleet import join

_VER = re.compile(r"Mentat fleet rules v(\S+)")
REL = ".claude/rules/fleet.md"


def header_version(text: str) -> str | None:
    m = _VER.search(text[:200])
    return m.group(1) if m else None


def state(repo: Path, agent: str | None = None, *, template: str | None = None, version: str | None = None) -> dict | None:
    """None, ha a repó nem flotta-tag (nincs manifest vagy fleet.md). `template`/`version`: a cél-kód sablonja."""
    repo = Path(repo)
    m, path = join.read_manifest(repo), repo / REL
    if not m or not path.is_file():
        return None
    agent = agent or m.get("agent")
    cur = path.read_text(encoding="utf-8")
    if template is not None and version:
        template = template.replace("@@FLEET_VERSION@@", version)
    new = join.render_rules(agent, template=template)
    have, want = join._sha(cur), join._sha(new)
    return {"agent": agent, "have_sha": have, "want_sha": want, "have_version": header_version(cur),
            "want_version": header_version(new), "modified": have != m.get("rules_sha"),
            "outdated": have != want, "new_text": new}


def describe(st: dict) -> str:
    s = f"szabályok {st['have_sha']} < telepített {st['want_sha']} (v{st['have_version']} < v{st['want_version']})"
    return s + (" — helyi módosítás, kézzel fésüld össze" if st["modified"] else "")


def warnings_for(entry: dict) -> list:
    """`fleet doctor` / `fleet status`: elavult szabályfájl repónként; naprakész repónál csend."""
    wd = str(entry.get("workdir") or "")
    repo = Path(wd.replace("%h", str(Path.home())))
    if not wd or not repo.is_dir():
        return []
    try:
        st = state(repo, entry["agent"])
    except (OSError, ValueError, KeyError):
        return []
    if not st or not st["outdated"]:
        return []
    fix = "" if st["modified"] else f" — `fleet upgrade {repo} --pr --rules`"
    return [f"{describe(st)}{fix}"]
