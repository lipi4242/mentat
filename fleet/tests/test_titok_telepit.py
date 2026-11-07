"""A titok-kapu felhasználói szintű telepítése (minden ~/.claude*/settings.json) és a doctor-jel.
2026-10-29: egy teszt a fejlesztő valódi $CLAUDE_CONFIG_DIR-jébe telepítette — ez itt rögzítve."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fleet import hookguard, titok_telepit as T


class Install(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        (self.home / ".claude-vilma").mkdir()
        (self.home / ".claude-vilma" / "settings.json").write_text(json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "mas-hook",
                                                                  "onFailure": "block"}]}]}, "model": "x"}))

    def pre(self, root):
        return json.loads((self.home / root / "settings.json").read_text())["hooks"]["PreToolUse"]

    def test_minden_gyokerbe_a_tobbi_hook_marad(self):
        T.install(self.home)
        for root in (".claude", ".claude-vilma"):
            own = [h for e in self.pre(root) for h in e["hooks"] if "titok-kapu" in h["command"]]
            self.assertEqual(len(own), 1, root)
            self.assertEqual(own[0]["onFailure"], "block")
        self.assertIn("mas-hook", json.dumps(self.pre(".claude-vilma")))
        self.assertTrue((self.home / ".mentat/bin/titok-kapu/current/titok_kapu.py").is_file())
        self.assertTrue(list((self.home / ".claude-vilma").glob("settings.json.bak-titok-*")))

    def test_idempotens(self):
        T.install(self.home)
        before = self.pre(".claude-vilma")
        T.install(self.home)
        self.assertEqual(self.pre(".claude-vilma"), before)

    def test_home_on_kivuli_claude_config_dir_erintetlen(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, outside, True)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(outside)}):
            T.install(self.home)
        self.assertFalse((outside / "settings.json").exists())

    def test_doctor_jel(self):
        root = self.home / ".claude-vilma"
        self.assertEqual(T.problems(root, self.home), [])  # a boxon még nincs titok-kapu: nem elvárás
        T.install(self.home)
        self.assertEqual(T.problems(root, self.home), [])
        (root / "settings.json").write_text("{}")
        self.assertIn("titok-kapu hiányzik", T.problems(root, self.home)[0])

    def test_hookguard_bekotve(self):
        with mock.patch.object(T, "problems", return_value=["x"]) as p:
            self.assertEqual(hookguard.secrets_gate_problems(Path("/a")), ["x"])
            p.assert_called_once()

    def test_a_telepitett_hook_tilt(self):
        """A kód a telepített helyéről, `python3 -I`-vel fut, és a szivárgó parancsot tiltja."""
        import subprocess
        import sys
        T.install(self.home)
        (self.home / ".config/szervezo").mkdir(parents=True)
        (self.home / ".config/szervezo/szervezo.env").write_text("A=hamis\n")
        cmd = json.dumps({"tool_name": "Bash", "cwd": str(self.home),
                          "tool_input": {"command": "cat ~/.config/szervezo/szervezo.env"}})
        r = subprocess.run([sys.executable, "-I", str(self.home / ".mentat/bin/titok-kapu/current/titok_kapu.py"),
                            "--hook"], input=cmd, capture_output=True, text=True, env={**os.environ, "HOME": str(self.home)})
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny", r.stderr)


class Csomag(unittest.TestCase):
    """CISO Q6: a nyilvános kiadásban nincs `security/`; a kapu a plugin másolatából települ, és ha
    az nincs meg, az install hangosan bukik (eddig egy jegyzet volt: csendben kapu nélkül maradt)."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_a_plugin_masolat_az_elso(self):
        self.assertEqual(T.SOURCES[0], T.PLUGIN_DIR / "hooks" / "identitas")

    def test_kod_nelkul_hangos_hiba(self):
        empty = self.home / "ures"
        empty.mkdir()
        with mock.patch.object(T, "SOURCES", (empty,)), mock.patch.object(T, "PLUGIN_SOURCE", empty):
            with self.assertRaises(T.SelfTestFailed) as cm:
                T.install(self.home)
        self.assertIn("titok_kapu.py", str(cm.exception))

    @unittest.skipUnless(T.DEV_SOURCE.is_dir() and not T.missing(T.PLUGIN_SOURCE),
                         "a plugin-másolat a plugin-sáv PR-jában (#109) jön; nyilvános exportban nincs security/")
    def test_a_ket_masolat_bajtra_egyezik(self):
        diff = [f for f in T.RUNTIME if (T.DEV_SOURCE / f).read_bytes() != (T.PLUGIN_SOURCE / f).read_bytes()]
        self.assertEqual(diff, [], "másold át: cp security/eszkozok/identitas/<f> plugin/hooks/identitas/")


class SelfTest(unittest.TestCase):
    """CISO Q5: egy hibás kiadás ne zárjon ki minden ágenst — és ne is menjen át csendben."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.src = self.home / "src"
        self.src.mkdir()
        for f in T.RUNTIME:
            shutil.copy2(T.source() / f, self.src / f)

    def broken(self, name, text):
        (self.src / name).write_text(text)
        with mock.patch.object(T, "source", return_value=self.src):
            with self.assertRaises(T.SelfTestFailed) as cm:
                T.install(self.home)
        self.assertFalse((self.home / ".mentat/bin/titok-kapu/current").exists())
        self.assertFalse((self.home / ".claude/settings.json").exists())
        return str(cm.exception)

    def test_mindent_tilto_kapu_nem_kerul_fel(self):
        self.assertIn("ártalmatlan", self.broken("titok_minta.py", "this is ( not python\n"))

    def test_mindent_atengedo_kapu_nem_kerul_fel(self):
        self.assertIn("átengedte", self.broken("titok_kapu.py", "import sys\nsys.exit(0)\n"))

    def test_halott_agens_hatar_nem_kerul_fel(self):
        self.assertIn("systemd", self.broken("agens_hatar.py", "raise ImportError('x')\n"))

    def test_jo_kod_atmegy(self):
        with mock.patch.object(T, "source", return_value=self.src):
            self.assertIn("önteszt rendben", T.install(self.home)[-1])


class HookStatus(unittest.TestCase):
    """2026-10-31, egy élő boxon: a `hook status` „minden Claude-gyökérben fent”-et írt, holott a kapu
    sosem települt (sem kód, sem leltár, a ~/.claude/settings.json-ban PreToolUse sem volt)."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "settings.json").write_text("{}")
        p = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        p.start()
        self.addCleanup(p.stop)

    def status(self):
        import argparse
        import contextlib
        import io
        from fleet import titok_cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = titok_cli.cmd_hook(argparse.Namespace(action="status"))
        return rc, out.getvalue()

    def test_sosem_telepitett_kapu_nem_zold(self):
        rc, out = self.status()
        self.assertNotIn("minden Claude-gyökérben fent", out)
        self.assertIn("NINCS telepítve", out)
        self.assertEqual(rc, 1)

    def test_telepitett_kapu_zold(self):
        T.install(self.home)
        rc, out = self.status()
        self.assertIn("minden Claude-gyökérben fent", out)
        self.assertEqual(rc, 0)

    def test_a_doctor_tovabbra_is_csak_hasznalt_kapunal_jelez(self):
        self.assertEqual(T.problems(self.home / ".claude", self.home), [])
        self.assertTrue(T.problems(self.home / ".claude", self.home, required=True))


if __name__ == "__main__":
    unittest.main()
