"""Egy titokfájl alakja — NEVEK és ujjlenyomatok, érték soha.

    describe(path) -> dict   osztály (env/json/pem/ismeretlen), kulcsnevek (env), mezőnevek (json),
                             private_key jelző, PEM-típus, méret, mód, dev+inode, sha256[:8] fájlra
                             és env-kulcsonként
    values(path) -> {név: érték}   CSAK folyamaton belül (move/audit); a kimenetbe sosem kerül

Az ujjlenyomat sha256(érték)[:8]: azonosít (ugyanaz-e a kulcs két helyen), de nem fejthető vissza.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

MAX = 1 << 20
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*=(.*)$")
PEM = re.compile(r"-----BEGIN ([A-Z0-9 ]+)-----")
SECRET_FIELD = re.compile(r"key|token|secret|passw|credential", re.I)


def fp(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()[:8]


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def _env(text: str) -> dict[str, str] | None:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return None
    pairs = [ENV_LINE.match(ln) for ln in lines]
    if sum(1 for m in pairs if m) * 2 < len(lines):
        return None
    return {m.group(1): _unquote(m.group(2)) for m in pairs if m}


def _read(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read(MAX)


def kind(raw: bytes) -> tuple[str, object]:
    text = raw.decode("utf-8", "replace")
    if PEM.search(text) and not text.lstrip().startswith("{"):
        return "pem", PEM.findall(text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return "json", data
    except ValueError:
        pass
    env = _env(text)
    return ("env", env) if env else ("ismeretlen", None)


def describe(path: Path) -> dict:
    st = path.stat()
    out = {"path": str(path), "size": st.st_size, "mode": oct(st.st_mode & 0o777), "dev": st.st_dev,
           "ino": st.st_ino}
    try:
        raw = _read(path)
    except OSError as e:
        return {**out, "class": "olvashatatlan", "error": type(e).__name__}
    cls, data = kind(raw)
    out.update({"class": cls, "fp": fp(raw)})
    if cls == "env":
        out["keys"] = [{"name": k, "fp": fp(v)} for k, v in data.items()]
    elif cls == "json":
        out["fields"] = sorted(data)
        out["private_key"] = "private_key" in data
    elif cls == "pem":
        out["pem"] = sorted(set(data))
    return out


def values(path: Path) -> dict[str, str]:
    """Név → érték, a mozgatáshoz és az audithoz. env: kulcsonként; json: a titok-jellegű szöveges
    mezők; pem és ismeretlen: az egész fájl `*` néven."""
    raw = _read(path)
    cls, data = kind(raw)
    if cls == "env":
        return dict(data)
    if cls == "json":
        return {k: v for k, v in data.items() if isinstance(v, str) and SECRET_FIELD.search(k)}
    return {"*": raw.decode("utf-8", "replace")}
