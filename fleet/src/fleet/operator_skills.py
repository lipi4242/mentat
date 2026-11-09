"""Operátor-skillek a box Claude Code-jába, a helyi fleet-checkoutból (symlink).

A /fleet:* plugin a nyilvános marketplace-ről, az ágensek saját fiókjába települ
(`fleet setup`). A boxon dolgozó fejlesztő ágens sessionje viszont nem flottatag, és
offline vagy szűrt boxon a marketplace el sem érhető. H5-mérés (2026-10-29): a fejlesztő
ágens skill-listájában egyetlen fleet-skill sem volt, ezért az összeolvasztás eljárását
(merge-agents) sosem látta. Ezért a CLI-vel együtt szállított operátor-skilleket a
felhasználó personal skill-könyvtárába linkeljük: ugyanaz a verzió látszik, mint amit a
`fleet` parancs tud, és a `git pull` a skillt is frissíti.

Csak a saját linkjeinket írjuk: egy létező, nem általunk tett fájlt/könyvtárat soha.
"""
from __future__ import annotations
import os
from pathlib import Path

from fleet import PLUGIN_DIR, kanari

#: A fejlesztő ágensnek szóló skillek (a többi plugin-skill a flottatagoké).
OPERATOR_SKILLS = ("merge-agents",)


def skills_dir(env=None, home: Path | None = None) -> Path:
    env = os.environ if env is None else env
    base = env.get("CLAUDE_CONFIG_DIR") or str((home or Path.home()) / ".claude")
    return Path(base) / "skills"


def _ours(link: Path, name: str) -> bool:
    """A symlink egy fleet-checkout `plugin/skills/<name>` könyvtárára mutat-e."""
    t = Path(os.readlink(link))
    return t.name == name and t.parent.name == "skills" and t.parent.parent.name == "plugin"


def _link(dst: Path, src: Path, name: str) -> None:
    """11-07: a skills/ a gyökér minden ágensének él → kanárival (kanari.py)."""
    kanari.guarded(f"operátor-skill: /{name}", [dst.parent.parent], lambda _r: dst.symlink_to(src),
                   home=Path.home())


def link_operator_skills(plugin_dir: Path = PLUGIN_DIR, target: Path | None = None) -> list[str]:
    """Idempotens; soha nem dob. Visszaad: jegyzetek (üres, ha nem kellett semmi)."""
    target = target or skills_dir()
    notes = []
    for name in OPERATOR_SKILLS:
        src = (plugin_dir / "skills" / name).resolve()
        if not (src / "SKILL.md").is_file():
            continue
        dst = target / name
        try:
            if dst.is_symlink():
                if Path(os.readlink(dst)) == src:
                    continue
                if not _ours(dst, name):
                    notes.append(f"skill: {dst} egy idegen symlink — nem írom felül")
                    continue
                dst.unlink()
            elif dst.exists():
                notes.append(f"skill: {dst} létezik és nem a flotta linkje — nem írom felül")
                continue
            target.mkdir(parents=True, exist_ok=True)
            _link(dst, src, name)
            notes.append(f"skill: /{name} → {src} (az új Claude-sessionökben látszik)")
        except kanari.Refused as e:
            notes.append(f"skill: {name} NEM linkelve — {e}")
        except OSError as e:
            notes.append(f"skill: {name} NEM linkelve ({e}); az eljárás: {src / 'SKILL.md'}")
    return notes
