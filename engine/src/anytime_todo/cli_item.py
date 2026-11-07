"""`item …` — backlog items: the spec side (the PM's) and reading.

    item new --project WEB --title T [--description D] [--priority 0-4] [--estimate N]
             [--pm HANDLE] [--parent REF] [--quote "exact words"] [--quote-ref WHERE]
             [--ac "Done when …"]... [--idem K]
    item show REF [--form [--lang hu|en]]      # REF = WEB-12 or the item id
    item edit REF [--title …] [--description …] [--priority N] [--estimate N] [--pm H]
             [--quote …] [--quote-ref …] [--rev N]
    item ac-add REF --text T | ac-edit REF AC_ID --text T | ac-remove REF AC_ID   [--rev N]
    item link REF (--url URL [--kind pr|issue|url] | --task ID) [--title T] [--rev N]

The state verbs (issue, take, handback, submit, accept, reject, hold, resume,
drop) are in cli_item_flow.py. --rev is always the item's rev, also for an AC.
"""
from __future__ import annotations

import argparse
from typing import Any

from . import cli_item_flow, form, work
from .api import TodoApiError, seg

SPEC = {"title": "title", "description": "description", "quote": "request_quote",
        "quote_ref": "request_ref", "pm": "pm"}


def _prio(text: str) -> int:
    if text not in ("0", "1", "2", "3", "4"):
        raise argparse.ArgumentTypeError("--priority is 0 (none), 1 (urgent) … 4 (low)")
    return int(text)


def _spec_args(p: argparse.ArgumentParser, new: bool) -> None:
    p.add_argument("--title", required=new)
    for opt in ("--description", "--pm", "--quote", "--quote-ref"):
        p.add_argument(opt)
    p.add_argument("--priority", type=_prio)
    p.add_argument("--estimate", type=int)


def add(sub) -> None:
    p = sub.add_parser("item", help="backlog items").add_subparsers(dest="verb", required=True)
    n = p.add_parser("new")
    n.add_argument("--project", required=True)
    _spec_args(n, True)
    n.add_argument("--parent")
    n.add_argument("--ac", action="append", default=[], help="an acceptance criterion (repeat)")
    work.add_idem(n)
    s = p.add_parser("show")
    s.add_argument("ref")
    s.add_argument("--form", action="store_true", help="print the AC form to fill for submit")
    s.add_argument("--lang", choices=sorted(form.HEAD), default="en")
    e = p.add_parser("edit")
    e.add_argument("ref")
    _spec_args(e, False)
    for verb, extra in (("ac-add", []), ("ac-edit", ["ac"]), ("ac-remove", ["ac"])):
        q = p.add_parser(verb)
        q.add_argument("ref")
        for x in extra:
            q.add_argument(x)
        if verb != "ac-remove":
            q.add_argument("--text", required=True)
        work.add_rev(q)
    k = p.add_parser("link")
    k.add_argument("ref")
    k.add_argument("--url")
    k.add_argument("--kind", choices=("pr", "issue", "url"), default="url")
    k.add_argument("--task")
    k.add_argument("--title")
    work.add_rev(e)
    work.add_rev(k)
    cli_item_flow.add(p)


def get(c, ref: str) -> dict[str, Any]:
    item = c.get_json("/items/" + seg(ref))
    if not isinstance(item, dict) or not item.get("id") or not isinstance(item.get("rev"), int):
        raise TodoApiError(f"todo API answered /items/{ref} without an item")
    return item


def _spec(a: argparse.Namespace) -> dict[str, Any]:
    out = {dst: work.text(getattr(a, src, None), src.replace("_", "-")) for src, dst in SPEC.items()}
    out.update(priority=a.priority, estimate=a.estimate)
    return {k: v for k, v in out.items() if v is not None}


def run(a: argparse.Namespace) -> int:
    c, _ = work.client()
    if a.verb == "new":
        acs = [work.required(t, "ac") for t in a.ac]
        body = {"project": a.project, **_spec(a), "parent": a.parent, "acs": acs or None}
        body["idem_key"] = work.idem(a.idem, "item", body)
        return work.show(c.send("POST", "/items", body))
    item = get(c, a.ref)
    if a.verb == "show":
        if a.form:
            print(form.render(item, a.lang), end="")
            return 0
        return work.show(item)
    path, rev = "/items/" + seg(item["id"]), a.rev if a.rev is not None else item["rev"]
    if a.verb == "edit":
        spec = _spec(a)
        if not spec:
            raise work.UsageError("item edit needs at least one field to change")
        return work.show(c.send("PATCH", path, {"set": spec, "expected_rev": rev}))
    if a.verb == "ac-add":
        return work.show(c.send("POST", path + "/acs",
                                {"text": work.required(a.text, "text"), "expected_rev": rev}))
    if a.verb in ("ac-edit", "ac-remove") and a.ac not in {x.get("id") for x in item.get("acs") or []}:
        raise work.UsageError(f"{a.ac} is not a live AC of {item.get('key') or item['id']}: "
                              "nothing sent (see `item show`)")
    if a.verb == "ac-edit":
        return work.show(c.send("PATCH", "/acs/" + seg(a.ac),
                                {"text": work.required(a.text, "text"), "expected_rev": rev}))
    if a.verb == "ac-remove":
        return work.show(c.send("POST", f"/acs/{seg(a.ac)}/remove", {"expected_rev": rev}))
    if a.verb == "link":
        if bool(a.url) == bool(a.task):
            raise work.UsageError("item link takes exactly one of --url or --task")
        body = ({"kind": "task", "task_id": a.task} if a.task else {"kind": a.kind, "url": a.url})
        return work.show(c.send("POST", path + "/links", {**body, "title": a.title, "expected_rev": rev}))
    return cli_item_flow.run(c, a, item, path, rev)
