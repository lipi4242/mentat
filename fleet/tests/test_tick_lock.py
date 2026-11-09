"""flotta-menedzser: a flotta tick-ütemezése tiszteli a karbantartási zárat (`fleet lock`): az ExecCondition
a renderelt és a már átvett unitban is ott van, és a shell-része valóban kihagyja a ticket, amíg a
zár él (lejárt, hiányzó vagy szemét zár: fut)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from fleet import tick_schedule as T


def _shell_of(line: str, home: Path) -> str:
    body = line[len("ExecCondition=/bin/sh -c '"):-1]
    return body.replace("%h", str(home)).replace("$$", "$").replace("%%", "%")


class LockCondition(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.home, True)
        (self.home / ".config/fleet/maintenance").mkdir(parents=True)
        self.lockf = self.home / ".config/fleet/maintenance/munkas"
        self.sh = _shell_of(T.lock_condition("munkas"), self.home)

    def rc(self):
        return subprocess.run(["/bin/sh", "-c", self.sh]).returncode

    def test_a_zar_alatt_kimarad_kulonben_fut(self):
        self.assertEqual(self.rc(), 0)                              # nincs zár
        self.lockf.write_text(str(time.time() + 600))
        self.assertEqual(self.rc(), 1)                              # él a zár: kimarad
        self.lockf.write_text(str(time.time() - 5))
        self.assertEqual(self.rc(), 0)                              # lejárt
        self.lockf.write_text("szemét")
        self.assertEqual(self.rc(), 0)                              # olvashatatlan: mint az is_locked
        self.lockf.write_text("")
        self.assertEqual(self.rc(), 0)

    def test_a_render_es_az_atvett_unit_is_megkapja(self):
        svc = T.render("munkas", self.home, {}, [])[f"{T.tick_unit('munkas')}.service"]
        self.assertIn(T.lock_condition("munkas"), svc.splitlines())
        old = "[Unit]\nDescription=x\n\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 -m anytime_engine.tick hourly\n"
        new = T.with_lock_condition(old, "munkas")
        lines = new.splitlines()
        self.assertEqual(lines[lines.index("Type=oneshot") + 1], T.lock_condition("munkas"))
        self.assertEqual(T.with_lock_condition(new, "munkas"), new)   # idempotens


if __name__ == "__main__":
    unittest.main()
