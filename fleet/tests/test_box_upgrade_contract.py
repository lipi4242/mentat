"""A box-upgrade és a VALÓDI `fleet` CLI közti szerződés: az `install` kilépési kódja
(0 kész · 3 függő · más bukott) és a `postcheck` első sora (`…: PENDING`/`FAILED`).
A box_agent_ops ezekre épít; ha a CLI kimenete elmozdul, ez a teszt bukik, nem a box.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fleet import cli, install_flow, postcheck as pc_mod  # noqa: E402
from fleet.box_agent_ops import postcheck as ops_postcheck  # noqa: E402
from fleet.box_ctx import Ctx, StepFailed  # noqa: E402

SIG = {k: {"state": "ok", "detail": "", "data": {}} for k in ("process", "schedule", "channel", "rc", "auth")}


def _cli(argv) -> tuple[int, str]:
    out = io.StringIO()
    a = cli.build_parser().parse_args(argv)
    with contextlib.redirect_stdout(out):
        rc = a.fn(a)
    return rc, out.getvalue()


class Contract(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(ROOT / "examples" / "registry")
        self._ia, self._pc = install_flow.install_agent, pc_mod.postcheck

    def tearDown(self):
        install_flow.install_agent, pc_mod.postcheck = self._ia, self._pc
        os.environ.pop("FLEET_REGISTRY") if self._env is None else os.environ.update(FLEET_REGISTRY=self._env)

    def test_install_exit_codes(self):
        for status, want in (("ok", 0), ("pending", 3), ("failed", 1)):
            install_flow.install_agent = lambda e, s=status: {"agent": e["agent"], "status": s, "notes": [],
                                                             "problems": [], "journal": []}
            self.assertEqual(_cli(["install", "demo-agent"])[0], want, status)

    def test_postcheck_head_line_is_parsed(self):
        for status, want in (("ok", "ok"), ("pending", "pending"), ("failed", None)):
            pc_mod.postcheck = lambda e, wait_s=90, s=status: {
                "agent": e["agent"], "status": s, "ok": s == "ok", "problems": ["x"] if s == "failed" else [],
                "pending": ["y"] if s == "pending" else [], "unknown": [], "waited_s": 0,
                "measure": {"signals": SIG}}
            rc, out = _cli(["postcheck", "demo-agent", "--wait", "0"])
            ctx = Ctx(home=Path("/nincs"), tag="v0", run=lambda cmd, rc=rc, out=out:
                      subprocess.CompletedProcess(cmd, rc, out, ""))
            if want is None:
                with self.assertRaises(StepFailed):
                    ops_postcheck(ctx, "demo-agent", 0)
            else:
                self.assertEqual(ops_postcheck(ctx, "demo-agent", 0), want, out)


if __name__ == "__main__":
    unittest.main()
