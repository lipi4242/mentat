#!/usr/bin/env python3
"""mentat_contract.py — the agreed task, in a file: what goes out, without what, to whom, for when.

    python3 .mentat/bin/mentat_contract.py [--repo .] [--lang hu|en] <command> ID ...
      draft ID --file PROPOSAL.json|-    write the proposal; prints the read-back for the USER
      approve ID --quote "<the USER's yes, verbatim>" [--version N]   only after their explicit yes
      show ID [--json]                   the contract, its status and approval
      diff ID --file PROPOSAL.json|-     what a new proposal changes; exit 3 = needs a new yes
      check-write ID [--fields a,b] [--recipients x@…,y@…] [--dates YYYY-MM-DD,…]
                                         does a planned write fit the approved contract?

The proposal's keys: mentat_contract_terms.py. Dates are absolute with a time zone ("next week"
is resolved with the USER first). A material change makes a new, unapproved version.
Exit: 0 ok/fits, 1 invalid or does not fit, 2 no approved contract (or no quote), 3 material change.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_accept as acc  # noqa: E402
import mentat_accept_checks as checks  # noqa: E402
import mentat_contract_store as store  # noqa: E402
import mentat_contract_terms as terms  # noqa: E402
import mentat_contract_text as text  # noqa: E402


def _proposal(src):
    raw = sys.stdin.read() if src == "-" else pathlib.Path(src).read_text(encoding="utf-8")
    t = json.loads(raw)
    errs = terms.validate(t)
    if errs:
        raise store.ContractError("the proposal is not usable:\n  " + "\n  ".join(errs))
    return terms.normalize(t)


def draft(a, lang):
    c, _changed = store.redraft(a.repo, a.id, _proposal(a.file))
    if c["status"] == "approved":
        print("no material change: the USER's approval of version %s stands" % c["version"])
    print(text.readback(c, lang))
    return 0


def approve(a, lang):
    if not (a.quote or "").strip():
        print("NOT APPROVED: approval needs the USER's explicit yes, verbatim (--quote \"<their words>\")")
        return 2
    c = store.approve(a.repo, a.id, a.quote, a.version)
    print("APPROVED %s version %s: \"%s\"" % (c["id"], c["version"], c["approval"]["quote"]))
    return 0


def show(a, lang):
    c = store.load(a.repo, a.id)
    if c is None:
        print("there is no contract %r" % a.id)
        return 2
    print(json.dumps(c, indent=2, ensure_ascii=False) if a.json else text.readback(c, lang))
    return 0


def diff(a, lang):
    c = store.load(a.repo, a.id)
    new = _proposal(a.file)
    changed = terms.material((c or {}).get("terms") or {}, new)
    if not changed:
        print("no material change")
        return 0
    old = (c or {}).get("terms") or {}
    for k in changed:
        print("%s: %s -> %s" % (k, json.dumps(old.get(k), ensure_ascii=False), json.dumps(new.get(k), ensure_ascii=False)))
    print("material change: draft it as a new version and ask the USER again")
    return 3


def check_write(a, lang):
    c, why = store.approved(a.repo, a.id)
    if c is None:
        print("NO WRITE: %s" % why)
        return 2
    t, s, probs = c["terms"], acc.T.get(lang, acc.T["en"]), []
    fields = [f.strip() for f in (a.fields or "").split(",") if f.strip()]
    excluded = (t.get("exclude") or {}).get("fields", [])
    probs.append(("excl_col", [f for f in fields if f in excluded]))
    probs.append(("extra_col", [f for f in fields if t.get("fields") and f not in t["fields"] + excluded]))
    people = [acc.load.address(p) for p in (a.recipients or "").split(",") if p.strip()]
    if people:
        probs.append(("stranger", checks.strangers(t, checks.Source(pathlib.Path(a.repo), t), people)))
    late = {}
    for d in [d.strip() for d in (a.dates or "").split(",") if d.strip() and t.get("window")]:
        key = checks.outside(t, d)
        if key:
            late.setdefault(key, []).append(d)
    probs += list(late.items())
    probs = [p for p in probs if p[1]]
    if not probs:
        print("FITS the approved contract %s (version %s)" % (c["id"], c["version"]))
        return 0
    print("DOES NOT FIT the approved contract %s:" % c["id"])
    print("\n".join("- " + acc.sentence(s, k, v) for k, v in probs))
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_contract.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", choices=["hu", "en"])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("draft", "approve", "show", "diff", "check-write"):
        sub.add_parser(name).add_argument("id")
    sub.choices["draft"].add_argument("--file", required=True)
    sub.choices["diff"].add_argument("--file", required=True)
    sub.choices["approve"].add_argument("--quote")
    sub.choices["approve"].add_argument("--version", type=int)
    sub.choices["show"].add_argument("--json", action="store_true")
    for flag in ("--fields", "--recipients", "--dates"):
        sub.choices["check-write"].add_argument(flag)
    a = p.parse_args(argv)
    lang = store.lang_and_dir(a.repo, a.lang)[0]
    run = {"draft": draft, "approve": approve, "show": show, "diff": diff, "check-write": check_write}
    try:
        return run[a.cmd](a, lang)
    except (store.ContractError, OSError, ValueError) as e:
        print("error: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
