"""A fake work store (SPEC §2) for the agent-side tests: records every request
and keeps just enough state (rev, stage, ACs, reports) for the CLI to run a
whole PM ↔ developer round. The real rules are the admin's; this fake only
checks expected_rev and idem_key, so the tests here prove the CLIENT's guards."""
from __future__ import annotations

import contextlib
import copy
import io
import os
from urllib.parse import parse_qs, urlparse

from _todo_fixture import BASE, FakeTodo, TodoCase

STAGES = {"issue": "issued", "take": "taken", "handback": "draft", "submit": "review",
          "accept": "done", "reject": "taken", "hold": "hold", "drop": "dropped"}


def item(iid: str = "I1", key: str = "WEB-7", acs=("AC1", "AC2"), stage: str = "draft") -> dict:
    return {"id": iid, "key": key, "title": "Kinél a labda nézet", "rev": 1, "stage": stage,
            "acs": [{"id": a, "text": f"Kész, ha {a} teljesül"} for a in acs], "reports": [],
            "links": []}


class FakeWork(FakeTodo):
    def do_GET(self):  # noqa: N802
        if not self._auth():
            return
        u, srv = urlparse(self.path), self.server
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = u.path[len(BASE):]
        if path == "/me":
            return self._send(200, {"id": "P-ROCKY", "handle": "rocky"})
        if path == "/changes":
            rows = [e for e in srv.events if e["seq"] > int(q["since"])]
            return self._send(200, rows[:int(q["limit"])])
        if path == "/cases/review-due":
            return self._send(200, srv.review_due)
        if path == "/items":
            return self._send(200, [i for i in srv.items.values() if i["stage"] == q.get("stage")])
        if path.startswith("/items/"):
            ref = path.split("/")[2]
            hit = next((i for i in srv.items.values() if ref in (i["id"], i["key"])), None)
            return self._send(200, hit) if hit else self._send(404, {"error": "no item"})
        if path.startswith("/tasks/"):
            t = srv.tasks.get(path.split("/")[2])
            return self._send(200, t) if t else self._send(404, {"error": "no"})
        return self._send(200, list(srv.tasks.values()))

    def do_PATCH(self):  # noqa: N802
        self.do_POST()

    def do_POST(self):  # noqa: N802
        if not self._auth():
            return
        srv, body = self.server, self.body or {}
        parts = urlparse(self.path).path[len(BASE):].strip("/").split("/")
        srv.sent.append((self.command, "/" + "/".join(parts), copy.deepcopy(body)))
        if parts in (["tasks"], ["items"]):
            if body["idem_key"] in srv.idem:
                return self._send(200, srv.idem[body["idem_key"]])
            row = {"id": f"N{len(srv.idem) + 1}", "rev": 1, **body}
            srv.idem[body["idem_key"]] = row
            return self._send(201, row)
        target = self._target(parts)
        if target is None:
            return self._send(404, {"error": "no"})
        if srv.race:                         # someone else wrote between our read and write
            srv.race, target["rev"] = False, target["rev"] + 1
        if body.get("expected_rev") != target["rev"]:
            return self._send(409, {"error": "stale rev", "current": copy.deepcopy(target)})
        target["rev"] += 1
        if parts[0] == "items" and len(parts) == 3:
            self._verb(target, parts[2], body)
        return self._send(200, target)

    def _target(self, parts):
        srv = self.server
        if parts[0] == "acs":
            return next((i for i in srv.items.values() if any(a["id"] == parts[1] for a in i["acs"])),
                        None)
        return (srv.items if parts[0] == "items" else srv.tasks).get(parts[1])

    @staticmethod
    def _verb(it: dict, verb: str, body: dict) -> None:
        it["stage"] = STAGES.get(verb, it["stage"])
        if verb == "submit":
            it["reports"].append({"round": body["round"], "results": body["results"]})


class WorkCase(TodoCase):
    handler = FakeWork

    def setUp(self):
        super().setUp()
        self.srv.events, self.srv.items, self.srv.sent = [], {}, []
        self.srv.idem, self.srv.review_due, self.srv.race = {}, [], False
        os.environ["ANYTIME_STATE_PATH"] = str(self.root / "data" / "state" / "anytime-state.json")
        self.configure()

    def cli(self, *argv) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = self.mod("cli").main(list(argv))
            except SystemExit as e:          # argparse usage errors
                rc = e.code
        return rc, out.getvalue() + err.getvalue()

    def sent(self, verb: str | None = None) -> list[tuple[str, str, dict]]:
        return [s for s in self.srv.sent if verb is None or s[1].endswith("/" + verb)]
