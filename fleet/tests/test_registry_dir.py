"""A registry helye kívülről jön (FLEET_REGISTRY → ~/.config/fleet/registry →
hiba). A hiányzó beállítás NEM üres flotta: érthető hibával kell megállni."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fleet  # noqa: E402
from fleet import cli  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "registry"


class TestRegistryDir(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ("FLEET_REGISTRY", "HOME")}
        self._home = tempfile.TemporaryDirectory()
        os.environ["HOME"] = self._home.name
        os.environ.pop("FLEET_REGISTRY", None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._home.cleanup()

    def _pointer(self, text: str) -> None:
        p = Path(self._home.name) / ".config" / "fleet" / "registry"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_env_wins(self):
        self._pointer("/nonexistent")
        os.environ["FLEET_REGISTRY"] = str(EXAMPLE)
        self.assertEqual(fleet.registry_dir(), EXAMPLE)

    def test_pointer_file_is_second(self):
        self._pointer(str(EXAMPLE) + "\n")
        self.assertEqual(fleet.registry_dir(), EXAMPLE)

    def test_nothing_configured_is_a_clear_error(self):
        with self.assertRaises(fleet.RegistryNotConfigured) as cm:
            fleet.registry_dir()
        self.assertIn("nincs registry beállítva", str(cm.exception))
        self.assertIn("FLEET_REGISTRY", str(cm.exception))

    def test_empty_pointer_file_is_not_configured(self):
        self._pointer("  \n")
        with self.assertRaises(fleet.RegistryNotConfigured):
            fleet.registry_dir()

    def test_missing_directory_is_an_error_not_an_empty_fleet(self):
        os.environ["FLEET_REGISTRY"] = str(Path(self._home.name) / "nincs-ilyen")
        with self.assertRaises(fleet.RegistryNotConfigured) as cm:
            fleet.registry_dir()
        self.assertIn("nem létező könyvtárra mutat", str(cm.exception))

    def test_validate_stops_with_exit_2(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cli.main(["validate"])
        self.assertEqual(rc, 2)
        self.assertIn("nincs registry beállítva", err.getvalue())

    def test_validate_on_example_is_green(self):
        os.environ["FLEET_REGISTRY"] = str(EXAMPLE)
        with redirect_stderr(io.StringIO()):
            import contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["validate"])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("2 ágens, 0 probléma", out.getvalue())

    def test_validate_on_dir_without_agents_json_is_red(self):
        os.environ["FLEET_REGISTRY"] = self._home.name
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cli.main(["validate"])
        self.assertEqual(rc, 1)
        self.assertIn("nincs agents.json", out.getvalue())


if __name__ == "__main__":
    unittest.main()
