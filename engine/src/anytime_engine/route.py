"""route — which executor gets which planned action (docs/concern-packs.md, "The executor").

The recorded executor (`--exec`, mentat.json components.engine.exec) is either generic (a
model run on a box: it gets every action, as always) or a pack's own (ANYTIME_PLUGIN["exec"],
e.g. the cases deliverer on a desktop). In the second case every action goes to its own pack's
executor, and an action whose pack names none is UNHANDLED: nobody does it, so the tick must
not report a clean success (tick.py: last-tick.json `unhandled`, exit 3).
"""
from __future__ import annotations

from typing import Any, Callable

from . import plugins

Executor = Callable[[dict[str, Any]], int]


class Routed:
    """An executor that splits the plan. After a call, `unhandled` lists the concerns nobody took."""

    def __init__(self, recorded: str, make: Callable[[str], Executor]):
        self.recorded, self.make = recorded, make
        self.unhandled: list[str] = []

    def groups(self, plan: dict[str, Any]) -> dict[str, list[dict]]:
        actions = plan.get("actions") or []
        if self.recorded not in plugins.pack_execs():   # generic: everything, as before
            return {self.recorded: list(actions)}
        out: dict[str, list[dict]] = {}
        self.unhandled = []
        for a in actions:
            cmd = plugins.pack_exec(a["concern"])
            if cmd:
                out.setdefault(cmd, []).append(a)
            else:
                self.unhandled.append(a["concern"])
        return out

    def __call__(self, plan: dict[str, Any]) -> int:
        rc = 0
        for cmd, actions in self.groups(plan).items():
            rc = self.make(cmd)({**plan, "actions": actions}) or rc
        return rc
