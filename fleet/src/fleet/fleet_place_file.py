"""A `fleet-place` blokk helye az AGENTS.md-ben. A jelölők pontosan a brainéi
(`<!-- mentat:managed:start <id> -->`, attribútum nélkül); a metaadat a blokkon
belül, az első sorban áll: `<!-- fleet-place agent=… mode=… hash=… -->`."""
from __future__ import annotations
import re

from fleet import fleet_place

ID = "fleet-place"
_RX = re.compile(r"<!-- mentat:managed:start fleet-place -->.*?<!-- mentat:managed:end fleet-place -->\n?", re.S)
_META = re.compile(r"<!-- mentat:managed:start fleet-place -->\n<!-- fleet-place ([^>]*?)-->")
_ANCHOR = re.compile(r"<!-- mentat:managed:end self-image -->\n?")


def block(fmap: dict, agent: str, mode: str) -> str:
    h = fleet_place.source_hash(fmap, agent, mode)
    return (f"<!-- mentat:managed:start {ID} -->\n"
            f"<!-- {ID} agent={agent} mode={mode} hash={h} -->\n"
            f"{fleet_place.body(fmap, agent, mode)}<!-- mentat:managed:end {ID} -->\n")


def parse_marker(text: str) -> dict | None:
    """{agent, mode, hash} a meglévő blokk jelölőjéből, vagy None."""
    m = _META.search(text or "")
    return dict(p.split("=", 1) for p in m.group(1).split() if "=" in p) if m else None


def place(text: str, new_block: str) -> str:
    """Csere a meglévő blokk helyén; különben a self-image után; különben a fájl elejére."""
    if _RX.search(text):
        return _RX.sub(lambda _m: new_block, text, count=1)
    m = _ANCHOR.search(text)
    if m:
        end = m.end()
        pre = text[:end] if text[:end].endswith("\n") else text[:end] + "\n"
        return pre + new_block + text[end:]
    return new_block + ("\n" + text if text else "")


def extract(text: str) -> str:
    """A teljes fleet-place blokk (jelölőkkel) vagy ''."""
    m = _RX.search(text or "")
    return m.group(0) if m else ""
