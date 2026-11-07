"""The brain's install step and the status report, run as a user would."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

CLI = pathlib.Path(__file__).resolve().parent / "mentat_cli.py"


def run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args, "--repo", str(root)],
                          capture_output=True, text=True)


class Cli(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())

    def init(self):
        return run(self.root, "init-brain", "--name", "Bob", "--language", "hu",
                   "--brain-root", "agy", "--version", "0.2.0")

    def test_init_brain_writes_both_files_and_gitignore(self):
        (self.root / ".gitignore").write_text(".env\n")
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(json.loads((self.root / "mentat.json").read_text()), {
            "schema": 1, "agent": {"name": "Bob", "language": "hu"},
            "components": {"brain": {"root": "agy"}}, "cases": {"backend": "markdown"}})
        self.assertEqual(json.loads((self.root / ".mentat/local.json").read_text()),
                         {"schema": 1, "installed": {"brain": "0.2.0"}})
        self.assertEqual((self.root / ".gitignore").read_text(), ".env\n.mentat/\n")

    def test_init_brain_is_idempotent_and_keeps_chosen_backend(self):
        self.init()
        manifest = json.loads((self.root / "mentat.json").read_text())
        manifest["cases"]["backend"] = "markdown-later"  # someone else's choice, unknown value
        (self.root / "mentat.json").write_text(json.dumps(manifest))
        self.init()
        got = json.loads((self.root / "mentat.json").read_text())
        self.assertEqual(got["cases"]["backend"], "markdown-later")
        self.assertEqual((self.root / ".gitignore").read_text().count(".mentat/"), 1)

    def test_status_names_elements_and_missing_synergies(self):
        self.init()
        out = run(self.root, "status")
        self.assertEqual(out.returncode, 0)
        self.assertIn("brain: present", out.stdout)
        self.assertIn("admin: not connected", out.stdout)
        self.assertIn("brain+engine: off", out.stdout)

    def test_status_offers_the_admin_as_todo_and_backlog(self):
        self.init()
        out = run(self.root, "status")
        self.assertIn("admin: not connected (the todo + backlog of Mentat", out.stdout)
        self.assertNotIn("coming soon", out.stdout)              # 0.5.0: the admin ships
        self.assertNotIn("mentat-admin checkout", out.stdout)

    def test_status_json_and_exit_code_on_unknown_schema(self):
        (self.root / "mentat.json").write_text('{"schema": 7}')
        out = run(self.root, "status", "--json")
        self.assertEqual(out.returncode, 2)
        self.assertTrue(json.loads(out.stdout)["diagnostic_only"])

    def test_init_refuses_bad_root(self):
        out = run(self.root, "init-brain", "--name", "Bob", "--language", "en",
                  "--brain-root", "../x", "--version", "0.2.0")
        self.assertNotEqual(out.returncode, 0)
        self.assertFalse((self.root / "mentat.json").exists())


if __name__ == "__main__":
    unittest.main()
