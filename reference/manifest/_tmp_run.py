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
# No test reads or writes the real user config: one HOME for the whole run (a test may set its own).
os.makedirs(os.path.join(RUN_TMP, "home"), exist_ok=True)
if not _inherited:  # USERPROFILE too: Windows Python's expanduser reads that, not HOME
    os.environ["HOME"] = os.environ["USERPROFILE"] = os.path.join(RUN_TMP, "home")
for _k in ("CLAUDE_CONFIG_DIR", "FLEET_REGISTRY"):
    os.environ.pop(_k, None)
if os.name == "nt":  # Claude Code's Git Bash has HOME == USERPROFILE; the tests move only HOME
    import ntpath
    import subprocess
    _expand = ntpath.expanduser

    def _home_first(p):
        h, s = os.environ.get("HOME"), os.fspath(p)
        if h and isinstance(s, str) and (s == "~" or s[:2] in ("~/", "~\\")):
            return h + s[1:]
        return _expand(p)

    ntpath.expanduser = os.path.expanduser = _home_first
    _popen = subprocess.Popen.__init__

    def _same_home(self, *a, **kw):
        env = kw.get("env")
        if env is not None and env.get("HOME"):
            kw["env"] = dict(env, USERPROFILE=env["HOME"])
        elif env is None and os.environ.get("HOME"):
            kw["env"] = dict(os.environ, USERPROFILE=os.environ["HOME"])
        _popen(self, *a, **kw)

    subprocess.Popen.__init__ = _same_home
