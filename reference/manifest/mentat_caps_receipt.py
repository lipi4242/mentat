"""The capability receipt: `where --find` writes it, `where --decide` records the decision once.

The receipt binds the request to the index (version + hash) and the candidates it saw. A
decision is refused when the index has changed since (STALE), when the named candidate is
not in the receipt, or when `new` lacks a candidate-specific reason. Zero candidates, or a
planned suite capability on top, is not decidable by the tool: `new` then needs the USER's
yes, verbatim (--approved), like `mentat_web.py deploy`.
"""
import hashlib
import json
import os
import pathlib
import time

DIR = pathlib.Path(".mentat") / "state" / "capability-receipts"
LEDGER = "_ledger.jsonl"  # the finder's own record: the guard trusts a receipt only with its line here
DECISIONS = ("use", "enable", "new")
MIN_WHY = 20


def recommend(cands):
    if not cands:
        return {"decision": None, "reason": "inconclusive"}
    top = cands[0]
    if top["lifecycle"] == "planned":
        return {"decision": "use", "candidate": top["id"], "via": "interim"}
    return {"decision": "use" if top["availability"] == "on" else "enable", "candidate": top["id"]}


def write(root, query, index, cands, rec):
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + os.urandom(2).hex()
    rel = DIR / (stamp + ".json")
    doc = {"schema": 1, "query": query, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "index": {"version": index["version"], "hash": index["hash"]},
           "verdict": "candidates" if cands else "inconclusive",
           "candidates": [{k: c[k] for k in ("id", "score", "availability", "lifecycle", "provenance")}
                          for c in cands],
           "recommendation": rec, "decision": None}
    path = pathlib.Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rel.as_posix()


def decide(root, receipt, decision, current_hash, candidate=None, why="", approved="", msg=None):
    """(exit code, message). 0 recorded, 1 refused, 2 not decidable without the USER's yes."""
    msg = msg or {}
    path = pathlib.Path(receipt)
    path = path if path.is_absolute() or path.exists() else pathlib.Path(root) / path
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1, "STOP no receipt: %s" % receipt
    if decision not in DECISIONS:
        return 1, "STOP decision must be one of: %s" % ", ".join(DECISIONS)
    if doc.get("decision"):
        return 1, "STOP already decided: %s" % doc["decision"]["decision"]
    if doc["index"]["hash"] != current_hash:
        return 1, "STALE %s" % msg.get("stale", "the index changed since this receipt: run where --find again")
    cands = {c["id"]: c for c in doc["candidates"]}
    if candidate and candidate not in cands:
        return 1, "STOP %s: %s" % (candidate, msg.get("not_in", "not a candidate of this receipt"))
    if decision in ("use", "enable"):
        if not cands:
            return 1, "STOP %s" % msg.get("nothing", "nothing to use: the search was inconclusive")
        if not candidate:
            return 1, "STOP --candidate <id> (%s)" % ", ".join(cands)
    else:
        if cands and not candidate:
            return 1, "STOP --candidate <%s> --why \"%s\"" % (doc["candidates"][0]["id"], msg.get("why", "what it lacks"))
        if len((why or "").strip()) < MIN_WHY:
            return 1, "STOP --why: %s" % msg.get("why", "what the closest candidate lacks, in a sentence")
        planned = not cands or doc["candidates"][0]["lifecycle"] == "planned" or \
            (candidate and cands[candidate]["lifecycle"] == "planned")
        if planned and not (approved or "").strip():
            return 2, "STOP %s" % msg.get("undecidable", "not decidable: new needs the USER's yes (--approved)")
    doc["decision"] = {"decision": decision, "candidate": candidate, "why": why or "",
                       "approved": approved or "", "decided_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    body = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    path.write_text(body, encoding="utf-8")
    line = {"receipt": path.name, "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "decided_at": doc["decision"]["decided_at"]}
    with open(path.parent / LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    return 0, "OK %s %s" % (decision, candidate or "")
