"""The Python tests leave nothing in the temp folder (2026-10-23: the bridge tests filled the
shared tmp quota of the thufir user; the Python suites left 40 folders per run too).
tests/_hermetic.py points tempfile and TMPDIR at one per-run folder and removes it at exit;
src/fleet cleans up after itself (release-tools: a separate PR, another track).
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import os
import site
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def leftovers(env_extra, *args, cwd=ROOT):
    fresh = tempfile.mkdtemp(prefix="zz-tmp-clean-", dir=_hermetic.REAL_TMP)
    env = dict(os.environ, TMPDIR=fresh, **env_extra)
    # The nested run sees what this run sees: the same interpreter, PYTHONPATH added to (not
    # replaced), and the user site of the REAL home (a box keeps pytest there; a tmp HOME hides it).
    if "PYTHONPATH" in env_extra and os.environ.get("PYTHONPATH"):
        env["PYTHONPATH"] = env_extra["PYTHONPATH"] + os.pathsep + os.environ["PYTHONPATH"]
    if site.ENABLE_USER_SITE and site.USER_BASE:
        env.setdefault("PYTHONUSERBASE", site.USER_BASE)
    env.pop("_FLEET_TEST_HOME", None)
    r = subprocess.run([sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True)
    left = sorted(os.listdir(fresh))
    for p in left:
        subprocess.run(["rm", "-rf", os.path.join(fresh, p)])
    os.rmdir(fresh)
    return r, left


class TmpClean(unittest.TestCase):
    def test_hermetic_removes_every_temp_folder_of_the_run(self):
        code = ("import sys; sys.path.insert(0, 'tests'); import _hermetic, tempfile, subprocess\n"
                "tempfile.mkdtemp(); tempfile.mkdtemp(prefix='x-')\n"
                "subprocess.run([sys.executable, '-c', 'import tempfile; tempfile.mkdtemp()'])\n")
        r, left = leftovers({}, "-c", code)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(left, [])

    def test_src_fleet_suite_leaves_nothing(self):
        for args in (["-m", "unittest", "discover", "-s", "src/fleet", "-p", "test_*.py", "-q"],):
            r, left = leftovers({"PYTHONPATH": "src", "HOME": tempfile.mkdtemp()}, *args)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertEqual(left, [], args)


if __name__ == "__main__":
    unittest.main()
