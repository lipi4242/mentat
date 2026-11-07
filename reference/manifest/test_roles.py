"""roles section: written by the brain CLI, resolved with MENTAT_ROLE."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

CLI = pathlib.Path(__file__).resolve().parent / "mentat_cli.py"


def run_env(root, extra, *args):
    return subprocess.run([sys.executable, str(CLI), *args, "--repo", str(root)],
                          capture_output=True, text=True,
                          env=dict(os.environ, **extra))


def run(root, *args):
    env = {k: v for k, v in os.environ.items() if k != "MENTAT_ROLE"}
    return subprocess.run([sys.executable, str(CLI), *args, "--repo", str(root)],
                          capture_output=True, text=True, env=env)


class Roles(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        run(self.root, "init-brain", "--name", "Bob", "--language", "hu",
            "--brain-root", "agy", "--version", "0.2.0")

    def test_roles_written_and_default_installed(self):
        r = run(self.root, "roles", "--default", "asszisztens", "--install", "fejleszto")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads((self.root / "mentat.json").read_text())
        self.assertEqual(m["roles"], {"default": "asszisztens",
                                      "installed": ["asszisztens", "fejleszto"]})

    def test_roles_bad_name_refused(self):
        r = run(self.root, "roles", "--default", "Bad Name")
        self.assertEqual(r.returncode, 1)

    def test_role_env_overrides_default_only_if_installed(self):
        run(self.root, "roles", "--default", "asszisztens", "--install", "fejleszto")
        ok = run_env(self.root, {"MENTAT_ROLE": "fejleszto"}, "role", "--json")
        out = json.loads(ok.stdout)
        self.assertEqual((out["role"], out["source"]), ("fejleszto", "env"))
        self.assertEqual(out["file"], str(pathlib.Path("agy") / "szerepek" / "fejleszto.md"))
        bad = run_env(self.root, {"MENTAT_ROLE": "kiado"}, "role")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("kiado", bad.stderr)

    def test_role_default_source(self):
        run(self.root, "roles", "--default", "asszisztens")
        r = run(self.root, "role", "--json")
        self.assertEqual(json.loads(r.stdout)["source"], "default")
        self.assertEqual(run(self.root, "role").stdout.strip(), "asszisztens")

    def test_role_without_roles_is_null(self):
        r = run(self.root, "role", "--json")
        self.assertEqual((r.returncode, json.loads(r.stdout)["role"]), (0, None))

    def _set_roles(self, roles):
        p = self.root / "mentat.json"
        m = json.loads(p.read_text())
        m["roles"] = roles
        p.write_text(json.dumps(m))

    def test_role_refuses_invalid_section(self):
        for roles, env in (({"default": "a", "installed": "fejleszto"}, "fej"),
                           ({"default": "kiado", "installed": ["a"]}, None)):
            self._set_roles(roles)
            r = run_env(self.root, {"MENTAT_ROLE": env} if env else {}, "role")
            self.assertEqual(r.returncode, 1, roles)
            self.assertIn("invalid_value", r.stderr)

    def test_role_name_with_trailing_newline_rejected(self):
        self.assertEqual(run(self.root, "roles", "--default", "x\n").returncode, 1)
        import mentat_rules
        self._set_roles({"installed": ["x\n"]})
        m = json.loads((self.root / "mentat.json").read_text())
        self.assertEqual(mentat_rules.evaluate(m, None)["errors"][0]["at"],
                         "roles.installed[0]")


if __name__ == "__main__":
    unittest.main()
