"""A `fleet-place` blokk tartalma a flottatérképből. Tiszta függvények.

Két mód: `inherited` (almappás ágens: a közös sorokat a gyökér-fájl adja, ide
csak a saját sorok kerülnek, ≤300 bájt) és `standalone` (minden sor, ≤600 bájt).
A határ a jelölők közti szövegre vonatkozik. Host, státusz, dátum nem kerülhet be.
"""
from __future__ import annotations
import hashlib
import json

MODES = {"inherited": 300, "standalone": 600}
MAX_TALKS = 5
ABOUT_MAX = 40
MAP_FILE = "fleet-map.json"
LABELS = {
    "hu": dict(owner="Tulajdonos", manager="Menedzser", map="Térkép", home="Otthon", up="Riport",
               talks="Beszél", more="+%d további: /fleet:roster", repos="Repók", maplink="%s (a registryben)"),
    "en": dict(owner="Owner", manager="Manager", map="Map", home="Home", up="Reports to",
               talks="Talks to", more="+%d more: /fleet:roster", repos="Repos", maplink="%s (in the registry)"),
}


class TooBig(ValueError):
    pass


def _lbl(fmap: dict, agent: str) -> dict:
    return LABELS[fmap["agents"][agent]["lang"]]


def root_lines(fmap: dict, lang: str) -> list[str]:
    """A közös sorok: ezeket a gyökér-összefoglaló adja inherited módban."""
    t = LABELS[lang]
    return [f"{t['owner']}: {fmap['owner']} · {t['manager']}: {fmap['manager']}",
            f"{t['map']}: {t['maplink'] % MAP_FILE}"]


def own_lines(fmap: dict, agent: str) -> list[str]:
    e, t = fmap["agents"][agent], _lbl(fmap, agent)
    h = e["home"]
    home = (h.get("repo") or h.get("url")) + (f"/{h['path']}" if h.get("path") else "")
    lines = [f"{t['home']}: {home}", f"{t['up']}: {e['reports_to']}"]
    talks = e["talks_to"]
    if talks:
        parts = [f"{x['agent']} ({x['about'][:ABOUT_MAX]})" for x in talks[:MAX_TALKS]]
        if len(talks) > MAX_TALKS:
            parts.append(t["more"] % (len(talks) - MAX_TALKS))
        lines.append(f"{t['talks']}: " + "; ".join(parts))
    if e["repos"]:
        lines.append(f"{t['repos']}: " + "; ".join(
            f"{r['repo']}{'/' + r['path'] if r.get('path') else ''} ({r['mode']})" for r in e["repos"]))
    return lines


def body_lines(fmap: dict, agent: str, mode: str) -> list[str]:
    own = own_lines(fmap, agent)
    return own if mode == "inherited" else root_lines(fmap, fmap["agents"][agent]["lang"]) + own


def body(fmap: dict, agent: str, mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"ismeretlen mód: {mode}")
    text = "\n".join(body_lines(fmap, agent, mode)) + "\n"
    if len(text.encode("utf-8")) > MODES[mode]:
        raise TooBig(f"{agent}: a blokk {len(text.encode('utf-8'))} bájt, a {mode} határ {MODES[mode]}")
    return text


def source_hash(fmap: dict, agent: str, mode: str) -> str:
    """A forrás hash-e: a blokk tartalmát meghatározó tények (nem a render szövege)."""
    src = {"agent": agent, "mode": mode, "lines": body_lines(fmap, agent, mode)}
    return hashlib.sha256(json.dumps(src, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
