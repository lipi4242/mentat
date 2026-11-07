"""Before any Google call that reaches other people: the approved contract's checks on the send plan.

The plan is the one mentat_accept.py reads (to/cc/bcc, or guests + guestsCanSeeOtherGuests); its
text (title, description, body) is checked for left-out data too. Fail-closed: no approved
contract, or a contract that does not say who may receive it, means no call.
"""
import json

import mentat_accept as accept
import mentat_accept_checks as checks
import mentat_accept_load as load
import mentat_contract_store as store

NO_CONTRACT = "it reaches other people, so it needs the USER's approved contract (--contract ID, see mentat_contract.py)"


def terms(root, cid):
    """(terms, None) or (None, why)."""
    if not cid:
        return None, NO_CONTRACT
    c, why = store.approved(root, cid)
    return (c["terms"], None) if c else (None, why)


def check(root, cid, plan):
    """(exit code, lines): 0 may go, 1 red, 2 no approved contract. Nothing is sent here."""
    t, why = terms(root, cid)
    if t is None:
        return 2, ["NOT SENT: %s" % why]
    au = t.get("audience") or {}
    if not (au.get("allowed") or au.get("from_records")):
        return 1, ["NOT SENT: contract %r does not say who may receive it (audience.allowed or "
                   "audience.from_records); draft it again with the USER" % cid]
    s = accept.T.get(store.lang_and_dir(root)[0], accept.T["en"])
    out = load.Output(json.dumps(plan, ensure_ascii=False), plan=plan)
    probs, people, _visible = accept.evaluate(root, t, out)
    if not probs:
        return 0, []
    return 1, [s["red"] % (s["to"] % len(set(people)))] + \
        ["- " + accept.sentence(s, k, v) for k, v in probs]


def eligible(root, cid):
    """The addresses the contract's audience allows by name (records + explicit addresses)."""
    t, why = terms(root, cid)
    if t is None:
        raise ValueError(why)
    return sorted(a for a in checks.allowed_set(t, checks.Source(root, t)) if a and not a.startswith("@"))
