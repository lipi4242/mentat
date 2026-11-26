"""Audit: egy ágens-repó AGENTS.md-jének fleet-place blokkja (megléte, sorrend, méret, drift, halott link).
Csak olvas."""
from __future__ import annotations
import re
from pathlib import Path

from fleet import fleet_place
from fleet import fleet_place_file as pf

SELF_START, SELF_END = "<!-- mentat:managed:start self-image -->", "<!-- mentat:managed:end self-image -->"
_LINK = re.compile(r"\]\(([^)#\s]+)")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def _body(block: str) -> str:
    lines = block.splitlines(keepends=True)
    return "".join(lines[2:-1])  # nyitó jelölő + metasor + ... + záró jelölő


def _links(repo: Path, name: str, text: str, mk) -> list:
    out = []
    for target in _LINK.findall(text):
        if not _SCHEME.match(target) and not (repo / target).exists():
            out.append(mk("dead-link", f"{name}: halott link a blokkban: {target}", agent=name, subject=target))
    return out


def check_repo(name: str, repo: Path, fmap: dict, registry_dir: Path, mk) -> list:
    path = repo / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = pf.extract(text)
    where = str(path)
    if not block:
        return [mk("block-missing", f"{name}: nincs fleet-place blokk ({where})", agent=name, subject=where)]
    out = []
    if SELF_START in text and text.find(SELF_END) > text.find(block):
        out.append(mk("block-order", f"{name}: a fleet-place a self-image előtt áll ({where})", agent=name, subject=where))
    marker = pf.parse_marker(text) or {}
    mode = marker.get("mode")
    body = _body(block)
    if mode in fleet_place.MODES and len(body.encode("utf-8")) > fleet_place.MODES[mode]:
        out.append(mk("block-size", f"{name}: a blokk {len(body.encode('utf-8'))} bájt, a {mode} határ {fleet_place.MODES[mode]}",
                      agent=name, subject=where))
    try:
        want = fleet_place.source_hash(fmap, name, mode)
        drift = marker.get("agent") != name or marker.get("hash") != want or body != fleet_place.body(fmap, name, mode)
    except (KeyError, TypeError, ValueError):
        drift = True
    if drift:
        out.append(mk("block-drift", f"{name}: a blokk eltér a térképtől ({where}); fleet map render {name}",
                      agent=name, subject=where))
    out += _links(repo, name, block, mk)
    if SELF_START in text:
        out += _links(repo, name, text[text.find(SELF_START):text.find(SELF_END)], mk)
    if "fleet-map.json" in block and not (registry_dir / "fleet-map.json").is_file():
        out.append(mk("dead-link", f"{name}: a blokk térkép-linkje halott (fleet-map.json)", agent=name, subject="fleet-map.json"))
    return out
