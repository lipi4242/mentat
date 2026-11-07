#!/usr/bin/env python3
"""mentat_accept.py — run the approved contract's checks on an output before it goes out or is called done.

    python3 .mentat/bin/mentat_accept.py [--repo .] [--lang hu|en] CONTRACT_ID OUTPUT [--recipients FILE] [--part]

OUTPUT is the file that would go out (CSV, JSON, Markdown) or a send plan (JSON with to/cc/bcc
or guests, see mentat_accept_load.py). --recipients adds a recipient list (one per line or comma
separated) to a file output. Prints GREEN or RED and one plain sentence per problem, saying what
would have gone out and to whom. Exit: 0 green, 1 red (do not send, do not call it done),
2 cannot check (no approved contract, unreadable output). --part: the output is one part of the
agreed set (a single reminder): a missing record is not an error, everything else still is.

Python API: `accept(root, contract_id, output_path, recipients=None, lang=None, part=False)
-> (exit code, lines)`. The engine's deliver step calls the CLI (anytime_cases/acceptance.py).
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_accept_checks as checks  # noqa: E402
import mentat_accept_load as load  # noqa: E402
import mentat_contract_store as store  # noqa: E402

T = {
    "en": {"green": "GREEN — this would go out: %s.", "red": "RED — do not send it and do not call it "
           "done. It would have gone out: %s. Problems:", "cannot": "CANNOT CHECK — %s",
           "rows": "%d rows (%s)", "to": "to %d recipients", "nobody": "to no one (a file)",
           "hidden": ", who cannot see each other",
           "extra_col": "it has a column that was not agreed: %s", "missing_col": "an agreed column is missing: %s",
           "no_columns": "I could not read any columns from it", "excl_col": "it contains a left-out column: %s",
           "excl_rec": "it contains a left-out record: %s", "excl_val": "it contains left-out data: %s",
           "outside": "a date is outside the agreed window: %s", "bad_date": "a date cannot be read: %s",
           "missing_rec": "an eligible record is missing: %s", "extra_rec": "it has a record that is not eligible: %s",
           "dup_rec": "a record appears twice: %s", "stranger": "it would go to someone outside the agreed audience: %s",
           "visible": "the recipients would see each other: %s", "more": " and %d more"},
    "hu": {"green": "ZÖLD — ez menne ki: %s.", "red": "PIROS — ne küldd el, és ne mondd késznek. "
           "Ez ment volna ki: %s. A hibák:", "cannot": "NEM ELLENŐRIZHETŐ — %s",
           "rows": "%d sor (%s)", "to": "%d címzettnek", "nobody": "senkinek (fájl)",
           "hidden": ", akik nem látják egymást",
           "extra_col": "olyan oszlop van benne, amiben nem állapodtunk meg: %s", "missing_col": "hiányzik egy megbeszélt oszlop: %s",
           "no_columns": "egyetlen oszlopot sem tudtam kiolvasni belőle", "excl_col": "kizárt oszlop van benne: %s",
           "excl_rec": "kizárt rekord van benne: %s", "excl_val": "kizárt adat van benne: %s",
           "outside": "egy dátum a megbeszélt időablakon kívül esik: %s", "bad_date": "egy dátum nem olvasható: %s",
           "missing_rec": "hiányzik egy jogosult rekord: %s", "extra_rec": "nem jogosult rekord van benne: %s",
           "dup_rec": "egy rekord kétszer szerepel: %s", "stranger": "a megbeszélt körön kívülre is menne: %s",
           "visible": "a címzettek látnák egymást: %s", "more": " és még %d"},
}


def sentence(s, key, items):
    shown = ", ".join(items[:3]) + (s["more"] % (len(items) - 3) if len(items) > 3 else "")
    return s[key] % shown if "%s" in s[key] else s[key]


def _people(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return [load.address(p) for p in text.replace(",", "\n").splitlines() if p.strip()]


def evaluate(root, terms, out, people=None, part=False):
    """(problems, what would go out) for an Output against the contract's checks."""
    src, probs = checks.Source(root, terms), []
    names, visible = terms.get("checks") or [], None
    if out.plan is not None:
        people, visible = load.recipients(out.plan)
    else:
        for name in names:
            if name in checks.TABLE:
                probs += checks.TABLE[name](terms, out, src)
    if out.plan is not None and "no_excluded" in names:
        probs += checks.no_excluded(terms, out, src)
    if people is not None and "recipients_allowed" in names:
        probs += checks.recipients_allowed(terms, out, src, people)
    if out.plan is not None and "visibility_hidden" in names:
        probs += checks.visibility_hidden(terms, out, src, visible)
    if part:
        probs = [p for p in probs if p[0] != "missing_rec"]
    return probs, people, visible


def accept(root, cid, output, recipients=None, lang=None, part=False):
    root = pathlib.Path(root)
    lang = store.lang_and_dir(root, lang)[0]
    s = T.get(lang, T["en"])
    c, why = store.approved(root, cid)
    if c is None:
        return 2, [s["cannot"] % why]
    try:
        out = load.read(pathlib.Path(output))
        people = _people(recipients) if recipients else None
        probs, people, visible = evaluate(root, c["terms"], out, people, part)
    except (OSError, ValueError, KeyError) as e:
        return 2, [s["cannot"] % e]
    n = len(set(people or []))
    if out.plan is None:
        what = s["rows"] % (len(out.rows), ", ".join(out.columns)) + " " + (s["to"] % n if people else s["nobody"])
    else:
        what = s["to"] % n + (s["hidden"] if not visible or len(visible) <= 1 else "")
    if not probs:
        return 0, [s["green"] % what]
    return 1, [s["red"] % what] + ["- " + sentence(s, k, v) for k, v in probs]


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_accept.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", choices=["hu", "en"])
    p.add_argument("contract")
    p.add_argument("output")
    p.add_argument("--recipients", help="file with the planned recipients, one per line")
    p.add_argument("--part", action="store_true", help="one part of the agreed set: a missing record is fine")
    a = p.parse_args(argv)
    try:
        code, lines = accept(a.repo, a.contract, a.output, a.recipients, a.lang, a.part)
    except store.ContractError as e:
        code, lines = 2, ["CANNOT CHECK — %s" % e]
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
