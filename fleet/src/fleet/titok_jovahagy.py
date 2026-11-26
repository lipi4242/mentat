"""Tételes tulajdonosi jóváhagyás a kulcsmozgatáshoz: ~/.mentat/titkok/jovahagyas/<id>.json.

    create(items, owner_text, ttl_min, approval_id=None) -> id
    check(id, op, name, src, dst)     Refused, ha hiányzik, lejárt, elhasznált, vagy a tétel nincs rajta
    claim(…)                          az írás ELŐTT: O_EXCL jelölőfájl, így két folyamat közül csak egy mehet át
    consume(…)                        a sikeres művelet után: a tétel elhasználva

Egy tétel: op (move|copy|put), name, from, to, why; a put tétel forrása mindig `stdin`. A tulajdonos szó szerinti igenje kötelező: ez
naplózott önbevallás, nem hitelesítés. Az `owner_msg` (a csatorna-üzenet azonosítója) utólag
ellenőrizhetővé teszi; nélküle a `fleet secrets audit` önbevallásként jelzi. Lejárat
legfeljebb 60 perc. Minden tétel egyszer használható; ha mind elfogyott, a fájl `consumed`.
v1 korlát: a fájlt az ágens is megírhatja (`fleet secrets approve`); v2 = a híd aláírja.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

from fleet import titok_hely as H

MAX_TTL_MIN = 60
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
OPS = ("move", "copy")
ITEM_OPS = OPS + ("put",)  # put: az érték a `fleet secrets put` stdin-jéről jön


class Refused(Exception):
    """A művelet nem mehet: az üzenet érték nélküli, magyar."""


def _path(approval_id: str, home: Path | None) -> Path:
    if not ID_RE.match(approval_id or ""):
        raise Refused("érvénytelen jóváhagyás-azonosító")
    return H.approvals_dir(home) / f"{approval_id}.json"


def parse_item(text: str) -> dict:
    """`OP:NÉV:HONNAN:HOVA:MIÉRT` — a miért tartalmazhat kettőspontot."""
    parts = text.split(":", 4)
    if len(parts) != 5 or parts[0] not in ITEM_OPS or not all(p.strip() for p in parts):
        raise Refused(f"a tétel alakja: {'|'.join(ITEM_OPS)}:NÉV:HONNAN:HOVA:MIÉRT (mind kitöltve)")
    op, name, src, dst, why = (p.strip() for p in parts)
    if (op == "put") != (src == "stdin"):
        raise Refused("a put tétel forrása `stdin` (put:NÉV:stdin:HOVA:MIÉRT), más tételé nem az")
    return {"op": op, "name": name, "from": src, "to": dst, "why": why, "consumed": False}


def create(items: list[dict], owner_text: str, ttl_min: int = MAX_TTL_MIN, approval_id: str | None = None,
           home: Path | None = None, now: float | None = None, owner_msg: str | None = None) -> str:
    if not items:
        raise Refused("legalább egy tétel kell (--item)")
    if not (owner_text or "").strip():
        raise Refused("a tulajdonos szó szerinti igenje kötelező (--owner-text)")
    if not 0 < ttl_min <= MAX_TTL_MIN:
        raise Refused(f"a lejárat 1–{MAX_TTL_MIN} perc")
    approval_id = approval_id or time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
    p = _path(approval_id, home)
    if p.exists():
        raise Refused(f"ez a jóváhagyás már létezik: {approval_id}")
    now = time.time() if now is None else now
    doc = {"schema": 1, "id": approval_id, "created": now, "expires": now + ttl_min * 60,
           "owner_text": owner_text.strip(), "owner_msg": (owner_msg or "").strip() or None, "items": items,
           "consumed": False}
    H.write_atomic(p, json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return approval_id


def self_declared(home: Path | None = None) -> list[str]:
    """A tulajdonosi üzenet-azonosító nélküli jóváhagyások (csak önbevallás)."""
    out = []
    for p in sorted(H.approvals_dir(home).glob("*.json")) if H.approvals_dir(home).is_dir() else []:
        try:
            doc = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if not doc.get("owner_msg"):
            out.append(str(doc.get("id") or p.stem))
    return out


def _marker(approval_id: str, op: str, name: str, src: str, dst: str, home: Path | None) -> Path:
    key = hashlib.sha256("\0".join((op, name, src, dst)).encode()).hexdigest()[:12]
    return _path(approval_id, home).with_suffix(f".{key}.used")


def claim(approval_id: str, op: str, name: str, src: str, dst: str, home: Path | None = None) -> None:
    """Atomikus, egyszeri lefoglalás az írás előtt; a második hívó Refused-ot kap (check→írás verseny)."""
    try:
        os.close(os.open(_marker(approval_id, op, name, src, dst, home),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600))
    except FileExistsError:
        raise Refused(f"ez a tétel már elhasználva: {op} {name}") from None


def check(approval_id: str, op: str, name: str, src: str, dst: str, home: Path | None = None,
          now: float | None = None) -> dict:
    p = _path(approval_id, home)
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError):
        raise Refused(f"nincs ilyen (olvasható) jóváhagyás: {approval_id}") from None
    now = time.time() if now is None else now
    if doc.get("consumed"):
        raise Refused(f"a jóváhagyás már elhasználva: {approval_id}")
    if not doc.get("owner_text") or float(doc.get("expires", 0)) < now or \
            float(doc.get("expires", 0)) - float(doc.get("created", 0)) > MAX_TTL_MIN * 60:
        raise Refused(f"a jóváhagyás lejárt vagy érvénytelen: {approval_id}")
    want = {"op": op, "name": name, "from": src, "to": dst}
    item = next((i for i in doc.get("items", []) if all(i.get(k) == v for k, v in want.items())), None)
    if item is None:
        raise Refused(f"ez a tétel ({op} {name}: {src} → {dst}) nincs a jóváhagyáson: {approval_id}")
    if item.get("consumed") or _marker(approval_id, op, name, src, dst, home).exists():
        raise Refused(f"ez a tétel már elhasználva: {op} {name}")
    return item


def consume(approval_id: str, op: str, name: str, src: str, dst: str, home: Path | None = None,
            now: float | None = None) -> dict:
    """A sikeres művelet UTÁN (a check() már átengedte): a tétel elhasználva."""
    p = _path(approval_id, home)
    doc = json.loads(p.read_text())
    want = {"op": op, "name": name, "from": src, "to": dst}
    item = next(i for i in doc["items"] if all(i.get(k) == v for k, v in want.items()))
    item["consumed"] = time.time() if now is None else now
    doc["consumed"] = all(i.get("consumed") for i in doc["items"])
    H.write_atomic(p, json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return item
