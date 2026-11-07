"""`me`, `ball`, `changes [--ack SEQ]` — who I am, what is on me, what changed.

    me                 my principal (from the token: the token IS the actor)
    ball               every open task, case and item whose ball is mine
    changes            the events for me after the cursor (JSON; `last_seq`, `more`)
    changes --ack SEQ  after handling the events up to SEQ: move the cursor there

Reading never moves the cursor (feed.py), so an event is never lost to a crash.
"""
from __future__ import annotations

import argparse

from . import feed, work


def add(sub) -> None:
    sub.add_parser("me", help="my principal")
    sub.add_parser("ball", help="everything whose ball is mine")
    ch = sub.add_parser("changes", help="events for me after the cursor")
    ch.add_argument("--ack", type=int, metavar="SEQ", help="handled up to SEQ: move the cursor")


def run(a: argparse.Namespace) -> int:
    if a.cmd == "changes" and a.ack is not None:
        _, s = work.client()
        feed.ack(s.api, s.handle, a.ack)
        print(f"cursor for {s.handle} at {a.ack}")
        return 0
    c, s = work.client()
    if a.cmd == "me":
        return work.show(c.get_json("/me"))
    if a.cmd == "ball":
        return work.show(c.get_json("/tasks", {"ball": s.handle, "status": "open", "kind": "all"}))
    return work.show(feed.read(c, s.handle))
