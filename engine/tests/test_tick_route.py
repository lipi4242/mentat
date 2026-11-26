#!/usr/bin/env python3
"""tick routing: an action goes to the executor that handles it, and one nobody handles is
counted, not silently dropped.

The hazard: the recorded executor on a desktop is the cases deliverer
(`python3 -m anytime_cases.deliver`), which skips every non-cases action with one stderr
line. With the todo pack beside it, `todo_esedekes` was planned every hour, done by nobody,
and the tick still stamped a clean success. A pack may now name its own executor
(ANYTIME_PLUGIN["exec"]); an action whose pack names none goes to the recorded executor
unless that executor IS another pack's own. What is left is `unhandled`: in last-tick.json,
in `anytime_engine last`, and the tick exits 3. A generic executor (a box agent's model
run) still gets every action, as before.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _engine_isolation import IsolatedTestCase  # noqa: E402
from anytime_engine import lasttick, tick  # noqa: E402
from anytime_engine.assembler import clear_providers  # noqa: E402
from anytime_engine.registry import clear  # noqa: E402

DELIVER_LIKE = "cat > delivered.json"   # stands in for the cases deliverer
CONCERN = '''from anytime_engine.registry import Concern, register
register(Concern(name="{n}", description="d", triggers=["hourly"],
                 should_run=lambda s: True, action="{n}", staleness_minutes=60))
'''


class _Route(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        clear()
        clear_providers()
        sys.path.insert(0, str(self.root))
        self.pack("cases_like", "c_morning", exec_cmd=DELIVER_LIKE)

    def tearDown(self):
        sys.path.remove(str(self.root))
        for m in [m for m in sys.modules if m.split(".")[0] in ("cases_like", "todo_like")]:
            del sys.modules[m]
        clear()
        clear_providers()
        super().tearDown()

    def pack(self, pkg, concern, exec_cmd=None):
        d = self.root / pkg
        d.mkdir()
        decl = {"name": pkg.replace("_", "-"), "engine": ">=0.4"}
        if exec_cmd:
            decl["exec"] = exec_cmd
        (d / "__init__.py").write_text(f"ANYTIME_PLUGIN = {decl!r}\n")
        (d / "concerns.py").write_text(CONCERN.format(n=concern))

    def tick(self, *argv, packs="cases_like,todo_like"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = tick.main(["hourly", "--plugins", packs, *argv])
        return rc, out.getvalue(), err.getvalue()

    def got(self, name):
        return [a["concern"] for a in json.loads((self.root / name).read_text())["actions"]]

    def last_tick(self):
        return json.loads((self.root / "data" / "state" / "last-tick.json").read_text())


class TestDesktop(_Route):
    def setUp(self):
        super().setUp()
        self.pack("todo_like", "t_due")

    def test_an_action_nobody_handles_is_counted_and_the_tick_is_not_clean(self):
        rc, _, err = self.tick("--exec", DELIVER_LIKE)
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.got("delivered.json"), ["c_morning"])
        self.assertIn("t_due", err)
        lt = self.last_tick()
        self.assertEqual((lt["handled"], lt["unhandled"]), (1, 1))

    def test_last_says_what_nobody_handled(self):
        self.tick("--exec", DELIVER_LIKE)
        text = lasttick.render(json.loads(lasttick.path().read_text()))
        self.assertIn("Unhandled: t_due", text)

    def test_a_pack_that_names_its_executor_gets_its_own_actions(self):
        (self.root / "todo_like" / "__init__.py").write_text(
            "ANYTIME_PLUGIN = {'name': 'todo-like', 'engine': '>=0.4', 'exec': 'cat > todo.json'}\n")
        rc, _, err = self.tick("--exec", DELIVER_LIKE)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.got("delivered.json"), ["c_morning"])
        self.assertEqual(self.got("todo.json"), ["t_due"])
        self.assertEqual((self.last_tick()["handled"], self.last_tick()["unhandled"]), (2, 0))


class TestBoxUnchanged(_Route):
    def setUp(self):
        super().setUp()
        self.pack("todo_like", "t_due")

    def test_a_generic_executor_still_gets_every_action(self):
        rc, _, err = self.tick("--exec", "cat > all.json")
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(self.got("all.json")), ["c_morning", "t_due"])
        self.assertFalse((self.root / "delivered.json").exists())
        self.assertEqual((self.last_tick()["handled"], self.last_tick()["unhandled"]), (2, 0))

    def test_without_an_executor_the_tick_only_decides_as_before(self):
        rc, out, err = self.tick()
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(a["concern"] for a in json.loads(out)["actions"]), ["c_morning", "t_due"])


class TestCasesPack(unittest.TestCase):
    def test_the_cases_pack_names_the_deliverer_setup_records(self):
        src = Path(__file__).resolve().parent.parent / "src"
        if not (src / "anytime_cases").is_dir():
            self.skipTest("cases pack not vendored here")
        from anytime_cases import ANYTIME_PLUGIN
        from anytime_engine.setup import DELIVER
        self.assertEqual(ANYTIME_PLUGIN.get("exec"), DELIVER)


if __name__ == "__main__":
    unittest.main()
