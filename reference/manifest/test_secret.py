"""A key the USER already pasted goes into the git-ignored env file at once, and its presence is
checked without the value ever being shown (the secret route the guard keeps open)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "mentat_secret.py"


def run(root, *args, stdin=""):
    return subprocess.run([sys.executable, "-I", str(TOOL), "--repo", str(root), *args], input=stdin,
                          capture_output=True, text=True, timeout=30)


class Secret(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".env\n")

    def test_put_writes_0600_and_has_never_prints_the_value(self):
        r = run(self.root, "put", "CF_TOKEN", stdin="  titkos-ertek-9  \n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = self.root / ".env"
        self.assertEqual(env.read_text(), "CF_TOKEN=titkos-ertek-9\n")
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        h = run(self.root, "has", "CF_TOKEN")
        self.assertEqual(h.returncode, 0)
        self.assertIn("SET CF_TOKEN", h.stdout)
        self.assertNotIn("titkos", r.stdout + h.stdout + r.stderr)
        self.assertIn("make a new one", r.stdout)  # it was in the chat: say so, plainly

    def test_has_says_missing_and_put_refuses_empty_or_unignored(self):
        self.assertEqual(run(self.root, "has", "NOPE").returncode, 1)
        self.assertEqual(run(self.root, "put", "X", stdin="\n").returncode, 1)
        self.assertEqual(run(self.root, "put", "X", "--env", "kulcs.txt", stdin="v\n").returncode, 1)
        self.assertFalse((self.root / "kulcs.txt").exists())


    def test_a_takeover_inventory_says_a_tracked_key_first(self):
        sys.path.insert(0, str(TOOL.parent))
        import mentat_init_inventory as inv
        (self.root / "notes.md").write_text("token = 'Zq8xT4pLm2Vn7Rk3Wc9Bh1'\n")
        subprocess.run(["git", "-C", str(self.root), "add", "notes.md"], check=True)
        out = "\n".join(inv.found_lines(inv.scan(self.root), "hu"))
        self.assertIn("TELL credential (password or key) in a file git keeps: notes.md:1", out)
        self.assertNotIn("Zq8xT4", out)


if __name__ == "__main__":
    unittest.main()
