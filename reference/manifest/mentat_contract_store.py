"""Where a contract lives and when it counts as approved.

One file per contract: `<brain>/contracts/<id>.json` (brain = mentat.json components.brain.root,
`agy` or `brain`), committed with the brain, so `git log` shows every version and its approval.

    {"schema": 1, "id": "...", "version": 2, "status": "draft"|"approved", "terms": {...},
     "approval": {"quote": "<the USER's words>", "at": "<UTC>", "version": 2, "digest": "..."} | null,
     "history": [{"version": 1, "terms": {...}, "approval": {...}}]}

An approval counts only while the digest of the material terms still matches: a hand edit of
an approved file voids it.
"""
import datetime
import json
import pathlib
import re

import mentat_contract_terms as terms
from mentat_brain import settings

SCHEMA = 1
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}$")


class ContractError(Exception):
    pass


def lang_and_dir(root, lang=None):
    lang, brain, _backend = settings(pathlib.Path(root), lang)
    return lang, pathlib.Path(root) / brain / "contracts"


def path(root, cid):
    if not ID.match(cid or ""):
        raise ContractError("contract id: lowercase letters, digits and dashes (e.g. dinner-guests)")
    return lang_and_dir(root)[1] / (cid + ".json")


def load(root, cid):
    p = path(root, cid)
    if not p.exists():
        return None
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ContractError("%s cannot be read: %s" % (p.name, e))
    if not isinstance(c, dict) or c.get("schema") != SCHEMA:
        raise ContractError("%s has an unknown schema" % p.name)
    return c


def save(root, c):
    p = path(root, c["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def approved(root, cid):
    """(contract, None) when it may be acted on, else (None, the reason in plain words)."""
    try:
        c = load(root, cid)
    except ContractError as e:
        return None, str(e)
    if c is None:
        return None, "there is no contract %r: draft it and get the USER's yes first" % cid
    if c.get("status") != "approved" or not c.get("approval"):
        return None, "version %s of %r awaits the USER's yes" % (c.get("version"), cid)
    if c["approval"].get("digest") != terms.digest(c.get("terms") or {}):
        return None, "%r was changed after approval: draft it again and ask the USER" % cid
    return c, None


def redraft(root, cid, new_terms):
    """Write a proposal; (contract, material keys). A material change = a new version, unapproved."""
    old = load(root, cid)
    if old is None:
        c = {"schema": SCHEMA, "id": cid, "version": 1, "status": "draft", "terms": new_terms,
             "approval": None, "history": []}
        save(root, c)
        return c, sorted(new_terms)
    changed = terms.material(old.get("terms") or {}, new_terms)
    if not changed:
        old["terms"] = new_terms  # only notes changed: the digest, so any approval, stands
    else:
        if old.get("approval"):
            old["history"].append({k: old[k] for k in ("version", "terms", "approval")})
        old.update(version=old["version"] + 1, status="draft", terms=new_terms, approval=None)
    save(root, old)
    return old, changed


def approve(root, cid, quote, version=None):
    c = load(root, cid)
    if c is None:
        raise ContractError("there is no contract %r to approve" % cid)
    if version is not None and version != c["version"]:
        raise ContractError("the USER saw version %s, the contract is at version %s: read it back again"
                            % (version, c["version"]))
    c.update(status="approved", approval={
        "quote": quote.strip(), "version": c["version"], "digest": terms.digest(c["terms"]),
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    save(root, c)
    return c
