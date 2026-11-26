"""Where no scheduler ticks (a desktop without the engine's schedule), a session starts with one
`tick hourly --once`, and the work it printed (the ball items) is in the session's context. The
engine decides whether to tick; the hook only runs it, bounded in time, and never fails on it."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import time
import unittest

from test_guard_kint import KintBase

FAKE_TICK = '''import pathlib, sys, time
pathlib.Path("tick-argv.json").write_text(__import__("json").dumps(sys.argv[1:]))
mode = pathlib.Path("fake-mode").read_text().strip() if pathlib.Path("fake-mode").exists() else "work"
if mode == "old":
    sys.exit("usage: tick: error: unrecognized arguments: --once")
if mode == "slow":
    time.sleep(30)
if mode == "work":
    print("## todo_labda\\nWEB-7 Reggeli kör: a labda nálad")
'''


class StartOnce(KintBase):
    roles = False

    def start(self):
        r = self.run_guard({"session_id": "s9", "cwd": str(self.root)}, None, args=["--session-start"])
        return (json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else "")

    def engine(self, mode="work", component=True):
        if component:
            doc = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
            doc["components"]["engine"] = {"path": "anytime_engine"}
            (self.root / "mentat.json").write_text(json.dumps(doc), encoding="utf-8")
        pkg = self.root / "anytime_engine"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "tick.py").write_text(FAKE_TICK, encoding="utf-8")
        (self.root / "fake-mode").write_text(mode, encoding="utf-8")

    def test_the_ball_items_of_a_once_tick_are_in_the_context(self):
        self.engine()
        ctx = self.start()
        self.assertIn("WEB-7 Reggeli kör", ctx)
        self.assertTrue("session-ind" in ctx or "session-start" in ctx, ctx)
        self.assertEqual(json.loads((self.root / "tick-argv.json").read_text(encoding="utf-8")), ["hourly", "--once"])

    def test_nothing_to_do_adds_nothing(self):
        self.engine(mode="quiet")
        ctx = self.start()
        self.assertTrue((self.root / "tick-argv.json").exists())
        self.assertNotIn("session-ind", ctx)    # the hook's own heading (hu) …
        self.assertNotIn("session-start", ctx)  # … or (en): only with work under it

    def test_no_engine_component_runs_no_tick(self):
        self.engine(component=False)
        self.start()
        self.assertFalse((self.root / "tick-argv.json").exists())

    def test_an_engine_without_once_is_quiet(self):
        self.engine(mode="old")
        self.assertNotIn("unrecognized", self.start())

    def test_a_slow_tick_does_not_hold_the_session_start(self):
        self.engine(mode="slow")
        t = time.monotonic()
        ctx = self.start()
        self.assertLess(time.monotonic() - t, 9)   # the hook's own timeout is 10 s
        self.assertNotIn("WEB-7", ctx)


if __name__ == "__main__":
    unittest.main()
