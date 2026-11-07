"""Every temp folder of a test run in ONE per-run folder, removed at exit (tests only).

Import it first in every test module. It points `tempfile` and the TMPDIR of child processes
at a fresh `mentat-test-tmp-*` folder and removes it when the process exits. 2026-10-24: the
suites left ~50 000 tmpXXXX folders on a box, and the shared tmp quota (EDQUOT) turned another
repo's gate red. Same pattern as the fleet's tests/_hermetic.py.
"""
import atexit
import os
import shutil
import tempfile

REAL_TMP = os.environ.get("_MENTAT_TEST_REAL_TMP") or tempfile.gettempdir()
os.environ["_MENTAT_TEST_REAL_TMP"] = REAL_TMP
_inherited = os.environ.get("_MENTAT_TEST_RUN_TMP")
if _inherited and os.path.isdir(_inherited):  # a child of a test run: the parent removes it
    RUN_TMP = _inherited
else:
    RUN_TMP = tempfile.mkdtemp(prefix="mentat-test-tmp-", dir=REAL_TMP)
    atexit.register(shutil.rmtree, RUN_TMP, True)
os.environ["TMPDIR"] = os.environ["_MENTAT_TEST_RUN_TMP"] = tempfile.tempdir = RUN_TMP
