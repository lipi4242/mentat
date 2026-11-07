import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fleet import bridge, BRIDGE_DIR


class Run:
    def __init__(self, rc=0, active=None, **by_verb):
        self.calls, self.rc, self.by, self.active = [], rc, by_verb, active

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        out = (self.active or "") if cmd[2] == "is-active" else ""
        return mock.Mock(returncode=self.by.get(cmd[2], self.rc), stdout=out)


def _install(tmp):
    dest = Path(tmp) / "a" / "sub-etha"
    Path(tmp, "a").mkdir()
    bridge.copy_bridge(dest)
    bridge.stamp(dest / "bridge.mjs", bridge.bridge_version())
    return dest


class DigestTest(unittest.TestCase):
    def test_clean_install_has_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _install(tmp)
            r = bridge.bridge_status([{"agent": "a"}], dest_root=Path(tmp))[0]
            self.assertEqual(r["changed"], [])
            self.assertFalse(r["drift"])

    def test_hand_edited_lib_is_drift_though_stamp_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _install(tmp)
            lib = sorted((dest / "lib").glob("*.mjs"))[0]
            lib.write_text(lib.read_text() + "\n// kezi\n")
            r = bridge.bridge_status([{"agent": "a"}], dest_root=Path(tmp))[0]
            self.assertEqual(r["installed"], r["current"])
            self.assertEqual(r["changed"], [f"lib/{lib.name}"])
            self.assertTrue(r["drift"])

    def test_missing_and_extra_files_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _install(tmp)
            (dest / "send.mjs").unlink()
            (dest / "lib" / "extra.mjs").write_text("x")
            ch = bridge.bridge_status([{"agent": "a"}], dest_root=Path(tmp))[0]["changed"]
            self.assertEqual(sorted(ch), ["lib/extra.mjs", "send.mjs"])

    def test_stamp_only_second_line_is_ignored_and_anchored(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _install(tmp)
            m = dest / "bridge.mjs"
            lines = m.read_text().splitlines(keepends=True)
            lines[1] = "// fleet-bridge 9.9.9 installed 2020-01-01\n"
            m.write_text("".join(lines))
            self.assertEqual(bridge.drift_files(dest), [])
            # nem horgonyzott / extra szoveg a bélyeg-soron: valodi valtozas
            lines[1] = "// fleet-bridge 9.9.9 installed 2020-01-01 EVIL\n"
            m.write_text("".join(lines))
            self.assertEqual(bridge.drift_files(dest), ["bridge.mjs"])


class RollbackTest(unittest.TestCase):
    def _setup(self, tmp):
        base = Path(tmp) / "a"
        base.mkdir()
        for n in ("sub-etha", "sub-etha.bak-20261001-000000", "sub-etha.bak-20261002-000000"):
            (base / n).mkdir()
            (base / n / "mark").write_text(n)
        (base / "telegram-state").mkdir()
        (base / "telegram-state" / "s").write_text("keep")
        return base

    def test_restores_newest_stop_swap_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            run = Run()
            r = bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
            self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha.bak-20261002-000000")
            self.assertEqual(run.calls, [["systemctl", "--user", "stop", "a-telegram-bridge.service"],
                                         ["systemctl", "--user", "start", "a-telegram-bridge.service"]])
            self.assertEqual(r["restored"], "sub-etha.bak-20261002-000000")
            rb = list(base.glob("sub-etha.rolledback-*"))
            self.assertEqual(len(rb), 1)
            self.assertEqual((rb[0] / "mark").read_text(), "sub-etha")
            self.assertEqual((base / "telegram-state" / "s").read_text(), "keep")

    def test_no_bak_raises_and_nothing_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "a"
            (base / "sub-etha").mkdir(parents=True)
            run = Run()
            with self.assertRaises(RuntimeError):
                bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
            self.assertTrue((base / "sub-etha").is_dir())
            self.assertEqual(run.calls, [])

    def test_symlink_bak_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "a"
            (base / "sub-etha").mkdir(parents=True)
            (base / "elsewhere").mkdir()
            (base / "sub-etha.bak-20261009-000000").symlink_to(base / "elsewhere")
            with self.assertRaises(RuntimeError):
                bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=Run())

    def test_failed_swap_restores_original_and_still_starts(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            run = Run()
            real = shutil.move
            n = {"i": 0}

            def flaky(src, dst):
                n["i"] += 1
                if n["i"] == 2:  # a bak -> sub-etha lepes
                    raise OSError("boom")
                return real(src, dst)
            with mock.patch("fleet.bridge_ops.shutil.move", flaky):
                with self.assertRaises(OSError):
                    bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
            self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha")
            self.assertEqual(run.calls[-1][2], "start")
            self.assertEqual(list(base.glob("sub-etha.rolledback-*")), [])

    def test_stop_fails_and_still_active_aborts_before_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            run = Run(stop=1, active="active\n")
            with self.assertRaises(RuntimeError):
                bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
            self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha")
            self.assertEqual(len(list(base.glob("sub-etha.bak-*"))), 2)
            self.assertNotIn("start", [c[2] for c in run.calls])

    def test_stop_fails_unproven_states_abort(self):
        for st in ("deactivating\n", "", "activating\n", "unknown\n"):
            with self.subTest(state=st), tempfile.TemporaryDirectory() as tmp:
                base = self._setup(tmp)
                run = Run(stop=1, active=st)
                with self.assertRaises(RuntimeError):
                    bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
                self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha")
                self.assertNotIn("start", [c[2] for c in run.calls])

    def test_stop_fails_but_failed_state_proceeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=Run(stop=1, active="failed\n"))
            self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha.bak-20261002-000000")

    def test_stop_fails_but_inactive_proceeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            run = Run(stop=1, active="inactive\n")
            bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=run)
            self.assertEqual((base / "sub-etha" / "mark").read_text(), "sub-etha.bak-20261002-000000")

    def test_start_failure_reflected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._setup(tmp)
            r = bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=Run(start=1))
            self.assertEqual(r["start_rc"], 1)

    def test_cli_nonzero_and_warns_on_start_failure(self):
        import io, contextlib
        from fleet import cli
        out = io.StringIO()
        res = {"agent": "a", "restored": "x", "unit": "u.service", "stop_rc": 0, "start_rc": 1}
        with mock.patch("fleet.bridge.rollback_bridge", return_value=res), \
                mock.patch.object(cli, "_entry_or_die", return_value={"agent": "a"}), \
                contextlib.redirect_stdout(out):
            rc = cli.cmd_bridge_rollback(mock.Mock(agent="a"))
        self.assertEqual(rc, 1)
        self.assertIn("FIGYELEM", out.getvalue())

    def test_rolledback_name_collision_does_not_nest(self):
        import datetime as dt
        with tempfile.TemporaryDirectory() as tmp:
            base = self._setup(tmp)
            fixed = dt.datetime(2026, 10, 18, 1, 2, 3)
            (base / "sub-etha.rolledback-20261018-010203").mkdir()
            with mock.patch("fleet.bridge_ops.datetime.datetime") as d:
                d.now.return_value = fixed
                bridge.rollback_bridge({"agent": "a"}, dest_root=Path(tmp), run=Run())
            self.assertFalse((base / "sub-etha.rolledback-20261018-010203" / "sub-etha").exists())
            self.assertEqual(len(list(base.glob("sub-etha.rolledback-*"))), 2)

    def test_cli_has_rollback(self):
        from fleet import cli
        self.assertTrue(hasattr(cli, "cmd_bridge_rollback"))


if __name__ == "__main__":
    unittest.main()
