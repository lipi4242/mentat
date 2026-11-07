"""agent-startup-seed.sh valódi tmux ellen: a parancsnak meg kell érkeznie a pane-be.

2026-10-14: a csupasz "=név" cél tmux 3.6 alatt "can't find pane"-t adott, a seed
200 s után feladta, és a frissen indult ágens tick nélkül maradt, miközben minden
jel zöld volt. Ez a teszt a tényleges kézbesítést nézi, nem a kilépési kódot.
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "bin" / "agent-startup-seed.sh"
TMUX = shutil.which("tmux")


@unittest.skipUnless(TMUX, "nincs tmux")
class StartupSeedDelivers(unittest.TestCase):
    def setUp(self):
        self.session = f"seedtest-{os.getpid()}"
        # a pane a "prompt"-ot imitálja: kiírja a jelzőt, aztán visszhangoz
        subprocess.run([TMUX, "new-session", "-d", "-s", self.session,
                        "sh -c 'echo bypass permissions; cat'"], check=True)

    def tearDown(self):
        subprocess.run([TMUX, "kill-session", "-t", f"={self.session}"], capture_output=True)

    def test_command_reaches_the_pane(self):
        env = dict(os.environ, AGENT_PROMPT_WAIT_S="20", AGENT_TMUX_BIN=TMUX)
        r = subprocess.run(["bash", str(SEED), self.session, "/startup-proba"],
                           env=env, capture_output=True, text=True, timeout=60)
        self.assertIn("bekuldve", r.stdout, r.stderr)
        time.sleep(0.5)
        pane = subprocess.run([TMUX, "capture-pane", "-p", "-t", f"={self.session}:"],
                              capture_output=True, text=True).stdout
        self.assertIn("/startup-proba", pane)


if __name__ == "__main__":
    unittest.main()
