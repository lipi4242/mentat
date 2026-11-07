"""leltar on a partial (blob:none) clone must not lazy-fetch forbidden blobs.

Live (0.3.0, a real onboarding): `git ls-tree -r -l` asked for every blob's size, and the
partial clone fetched them all on demand: 0/46 forbidden blobs local before, 46/46 after."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import leltar


def git(*a, cwd=None, env=None):
    return subprocess.run(["git", *a], cwd=cwd, env=env, capture_output=True, text=True)


class LeltarLazyFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        src = self.tmp / "src"
        (src / "ugyfelek").mkdir(parents=True)
        (src / "ugyfelek" / "private.json").write_text('{"x": 1}\n')
        (src / "README.md").write_text("# web\n")
        git("init", "-q", str(src))
        git("-c", "user.name=T", "-c", "user.email=t@example.com", "add", "-A", cwd=src)
        git("-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "i", cwd=src)
        self.dst = self.tmp / "dst"
        git("clone", "-q", "--no-checkout", "--filter=blob:none",
            "--upload-pack=git -c uploadpack.allowFilter=true upload-pack", "file://%s" % src, str(self.dst))
        git("-C", str(self.dst), "sparse-checkout", "set", "--no-cone", "/*", "!**/ugyfelek/private.json")
        git("-C", str(self.dst), "checkout", "-q")

    def local(self, rel):
        env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
        return git("-C", str(self.dst), "cat-file", "-e", "HEAD:" + rel, env=env).returncode == 0

    def test_inventory_leaves_forbidden_blobs_remote(self):
        self.assertFalse(self.local("ugyfelek/private.json"))  # precondition: partial clone
        inv = leltar._repo(self.dst, ["ugyfelek/private.json"])
        self.assertIn({"path": "ugyfelek/private.json", "tiltott": True}, inv["files"])
        self.assertFalse(self.local("ugyfelek/private.json"))
        readme = next(f for f in inv["files"] if f["path"] == "README.md")
        self.assertEqual(readme["size"], len("# web\n"))


if __name__ == "__main__":
    unittest.main()
