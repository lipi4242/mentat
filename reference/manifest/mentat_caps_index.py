"""The capability index: the curated suite catalog (capabilities/*.json, shipped with the
product) plus the agent's own inventory, as one list with a version and a content hash.

The catalog only DECLARES; availability is observed separately (mentat_caps_probe.py).
"""
import hashlib
import json
import pathlib

import mentat_caps_own as own

HERE = pathlib.Path(__file__).resolve().parent
REPO = "https://raw.githubusercontent.com/lipi4242/mentat/"  # + "v<version>/"


def version():
    for p in (HERE / "release.json", HERE.parent.parent / "release.json"):
        try:
            return str(json.loads(p.read_text(encoding="utf-8"))["version"])
        except (OSError, ValueError, KeyError):
            continue
    return "0"


def _subst(value, ver):
    if isinstance(value, str):
        return value.replace("{BASE}", "%sv%s/" % (REPO, ver)).replace("{VERSION}", ver)
    if isinstance(value, list):
        return [_subst(v, ver) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v, ver) for k, v in value.items()}
    return value


def catalog():
    out = []
    for f in sorted((HERE / "capabilities").glob("*.json")):
        out += json.loads(f.read_text(encoding="utf-8"))
    return out


def build(root, brain):
    ver = version()
    entries = [_subst(e, ver) for e in catalog()] + own.inventory(root, brain)
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"version": ver, "hash": digest[:16], "entries": entries, "base": "%sv%s/" % (REPO, ver)}


def localize(value, lang):
    """A {hu, en} text in the agent's language; a plain value as it is."""
    if isinstance(value, dict) and set(value) <= {"hu", "en"}:
        return value.get(lang) or value.get("en") or ""
    return value


def doc_url(e, lang, base):
    """Suite docs are fetched from the pinned release; own docs are paths in this repo."""
    doc = localize(e.get("docs"), lang) or ""
    return base + doc if doc and e.get("provenance") == "suite" and not doc.startswith("http") else doc
