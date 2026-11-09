"""`fleet wake` — elsődleges a todo-feladat a meglévő mentat-todo klienssel; tartalék a peer-üzenet."""
import _hermetic  # noqa: F401
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fleet import wake as w

E = {"agent": "kiado-release-agent", "rc_name": "kiado", "bridge": {"unit": "kiado-telegram-bridge.service"},
     "tick_gate": {"release": {"todo_handle": "kiado"}}}


class Wake(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.home, True)
        self.calls = []

    def fake_run(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"id": "t_1"}), "")

    def go(self, principal="p_kiado", bridge="fut", entry=E):
        return w.wake(entry, "PR #12: kapuzd/mergeld", "https://github.com/o/r/pull/12", home=self.home,
                      run=self.fake_run, principal=lambda h, me, home: principal if h == "kiado" else None,
                      bridge=lambda e, r: bridge)

    def test_todo_feladat_a_principalra_hid_fut(self):
        code, out = self.go()
        self.assertEqual((code, out["task"], out["fallback"]), (0, "t_1", None))
        cmd = self.calls[0]
        self.assertEqual(cmd[:3], ["mentat-todo", "task", "new"])
        self.assertEqual(cmd[cmd.index("--assignee") + 1], "p_kiado")
        self.assertIn("https://github.com/o/r/pull/12", cmd[cmd.index("--description") + 1])

    def test_masik_boxon_a_hid_nem_merheto_a_feladat_eleg(self):
        self.assertEqual(self.go(bridge="ismeretlen")[0], 0)

    def test_nincs_principal_tartalek_peer_uzenet(self):
        code, out = self.go(principal=None)
        self.assertEqual((code, self.calls), (3, []))
        self.assertEqual(out["fallback"]["send"], "/rc kiado — PR #12: kapuzd/mergeld (https://github.com/o/r/pull/12)")

    def test_nem_futo_hid_tartalek_a_feladat_mellett(self):
        code, out = self.go(bridge="nem fut")
        self.assertEqual((code, out["task"]), (3, "t_1"))
        self.assertIn("híd", out["fallback"]["why"])

    def test_handle_a_registrybol_vagy_a_handles_fajlbol(self):
        self.assertEqual(w.target_handle(E, self.home), "kiado")
        f = self.home / ".config" / "todo" / "handles"; f.parent.mkdir(parents=True)
        f.write_text("dev-x=devh\n")
        self.assertEqual(w.target_handle({"agent": "dev-x"}, self.home), "devh")
        self.assertEqual(w.target_handle({"agent": "z"}, self.home), "z")


if __name__ == "__main__":
    unittest.main()
