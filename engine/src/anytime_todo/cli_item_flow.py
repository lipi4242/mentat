"""The PM ↔ developer verbs of a backlog item (SPEC §3.2).

    PM:   issue REF --dev HANDLE · accept REF --checked · reject REF --fail AC=why... --note N
          hold REF --note N · resume REF · drop REF --note N
    dev:  take REF · handback REF --note N · submit REF --form FILE

Who may do what is the server's rule (the token's principal is the actor);
these commands only shape the request and refuse what can never pass:
a form that does not match the live ACs, an accept while an AC is not met,
a reject with no failed AC or no reason.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import form, form_check, work

NOTE_VERBS = ("handback", "hold", "drop")


def add(p) -> None:
    for verb in ("issue", "take", "handback", "submit", "accept", "reject", "hold", "resume", "drop"):
        q = p.add_parser(verb)
        q.add_argument("ref")
        if verb == "issue":
            q.add_argument("--dev", required=True, help="the developer's handle (may be you)")
        if verb in NOTE_VERBS + ("reject",):
            q.add_argument("--note", required=True)
        if verb == "submit":
            q.add_argument("--form", required=True, help="the filled form of `item show REF --form`")
        if verb == "accept":
            q.add_argument("--checked", action="store_true", required=True,
                           help="you checked every result against its evidence")
        if verb == "reject":
            q.add_argument("--fail", action="append", default=[], metavar="AC_ID=WHY",
                           help="an AC that does not pass, with the reason (repeat)")
        work.add_rev(q)


def _last(item: dict[str, Any]) -> dict[str, Any]:
    reports = item.get("reports") or []
    if not reports:
        raise work.UsageError("nothing to decide: the item has no submitted report")
    return max(reports, key=lambda r: int(r.get("round") or 0))


def _submit(item: dict[str, Any], path: str) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise work.UsageError(f"cannot read the form {path}: {e.strerror}") from None
    f = form.parse(text)
    form_check.check(f, item)
    return {"round": f["round"], "summary": f["summary"], "body": f["body"],
            "head_sha": f["head_sha"], "links": [{"kind": "pr", "url": u} for u in f["prs"]] or None,
            "results": [{k: r[k] for k in ("ac_id", "verdict", "evidence")} for r in f["results"]]}


def _accept(item: dict[str, Any]) -> dict[str, Any]:
    results = _last(item).get("results") or []
    open_ = [r["ac_id"] for r in results if r.get("verdict") not in ("met", "na")]
    if open_:
        raise work.UsageError("cannot accept, not met: " + ", ".join(open_) + " — reject instead")
    return {"checks": [{"ac_id": r["ac_id"], "pm_ok": 1} for r in results]}


def _reject(item: dict[str, Any], fails: list[str], note: str) -> dict[str, Any]:
    results = _last(item).get("results") or []
    known = {r["ac_id"] for r in results}
    why: dict[str, str] = {}
    for f in fails:
        ac, sep, reason = f.partition("=")
        if not sep or not reason.strip():
            raise work.UsageError(f"--fail {f!r}: write it as AC_ID=reason")
        if ac not in known:
            raise work.UsageError(f"--fail {ac}: not a result of the current round")
        why[ac] = reason.strip()
    if not why:
        raise work.UsageError("reject needs at least one --fail AC_ID=reason")
    checks = [{"ac_id": r["ac_id"], "pm_ok": 0, "pm_note": why[r["ac_id"]]} if r["ac_id"] in why
              else {"ac_id": r["ac_id"], "pm_ok": 1} for r in results]
    return {"checks": checks, "note": note}


def run(c, a: argparse.Namespace, item: dict[str, Any], path: str, rev: int) -> int:
    body: dict[str, Any] = {}
    if a.verb == "issue":
        body = {"dev": work.required(a.dev, "dev")}
    elif a.verb in NOTE_VERBS:
        body = {"note": work.required(a.note, "note")}
    elif a.verb == "submit":
        body = _submit(item, a.form)
    elif a.verb == "accept":
        body = _accept(item)
    elif a.verb == "reject":
        body = _reject(item, a.fail, work.required(a.note, "note"))
    elif a.verb not in ("take", "resume"):
        raise work.UsageError(f"unknown item verb {a.verb}")   # pragma: no cover
    return work.show(c.send("POST", f"{path}/{a.verb}", {**body, "expected_rev": rev}))
