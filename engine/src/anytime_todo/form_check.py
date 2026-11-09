"""The client-side guards of a parsed AC form (form.py); the server checks the same again."""
from __future__ import annotations

import re
from typing import Any

from .form import VERDICTS, FormError, next_round


def check(form: dict[str, Any], item: dict[str, Any]) -> None:
    """The client-side guards; the server checks the same again (SPEC §3.2)."""
    errs: list[str] = []
    if form["item"] != item["id"]:
        errs.append(f"the form is for item {form['item']}, not {item['id']}")
    if form["round"] != next_round(item):
        errs.append(f"the form is for round {form['round']}, the item expects {next_round(item)}: "
                    "get a fresh form")
    ids = [r["ac_id"] for r in form["results"]]
    live = [a["id"] for a in item.get("acs") or []]
    if len(ids) != len(set(ids)):
        errs.append("an AC appears twice: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    if missing := [i for i in live if i not in ids]:
        errs.append("AC missing from the form: " + ", ".join(missing))
    if unknown := [i for i in ids if i not in live]:
        errs.append("not a live AC of this item: " + ", ".join(unknown))
    texts = {a["id"]: " ".join(str(a["text"]).split()) for a in item.get("acs") or []}
    for r in form["results"]:
        if r["ac_id"] in texts and " ".join(r["quoted"].split()) != texts[r["ac_id"]]:
            errs.append(f"AC {r['ac_id']} changed since the form was made: get a fresh form")
        if r["verdict"] not in VERDICTS:
            errs.append(f"AC {r['ac_id']}: verdict must be one of {', '.join(VERDICTS)}")
        if not r["evidence"]:
            errs.append(f"AC {r['ac_id']}: evidence is required (a test name, file:line, a log)")
    if not form["summary"]:
        errs.append("Meta: summary is required")
    if form["head_sha"] and not re.fullmatch(r"[0-9a-f]{7,40}", form["head_sha"]):
        errs.append(f"Meta: head_sha must be a git commit hash, 7-40 hex: {form['head_sha']!r}")
    for pr in form["prs"]:
        if not re.fullmatch(r"https?://\S+", pr):
            errs.append(f"Meta: pr must be a full http(s) URL (https://github.com/OWNER/REPO/pull/N), "
                        f"or leave the line empty: {pr!r}")
    if errs:
        raise FormError("the form cannot be submitted:\n- " + "\n- ".join(errs))
