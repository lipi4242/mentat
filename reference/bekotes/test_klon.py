"""$BK klon: forbidden files never land on disk; check `tiltott-lemez` catches one put back."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import shutil
import unittest

from _bekotes_repo import BIZ, bk, done, git, make_agent, write


class Klon(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()  # the fixture itself clones zoldag-web with $BK klon
        self.addCleanup(shutil.rmtree, self.root, True)
        self.web = self.root / "munka/zoldag-web"

    def test_forbidden_file_absent_others_present(self):
        self.assertTrue((self.web / "README.md").is_file())
        self.assertTrue((self.web / "docs/a.md").is_file())
        self.assertFalse((self.web / "ugyfelek/private.json").exists())
        r = subprocess_ls(self.web)
        self.assertIn("ugyfelek/private.json", r)  # still in history: leltar names it

    def test_nested_and_case_variants_are_excluded_too(self):
        origin = self.root / ".home/origin2"
        write(self.root, ".home/origin2/a/ugyfelek/private.json", "x\n")
        write(self.root, ".home/origin2/kepek/foto-001.jpg", "x\n")
        write(self.root, ".home/origin2/ok.txt", "x\n")
        git(origin, "init", "-q")
        git(origin, "add", "-A")
        git(origin, "commit", "-q", "-m", "i")
        r = bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "zoldag-web",
               "--from", str(origin), "--dest", "munka/masik")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = sorted(p.relative_to(self.root / "munka/masik").as_posix()
                       for p in (self.root / "munka/masik").rglob("*") if p.is_file() and ".git" not in p.parts)
        self.assertEqual(files, ["ok.txt"])

    def test_a_whole_folder_is_excluded_at_any_depth(self):
        """BEKOTES: `folder/**` excludes the whole folder, at any depth (0.3.1)."""
        origin = self.root / ".home/origin3"
        for rel in ("archiv/a.md", "x/archiv/b.md", "ok.txt"):
            write(self.root, ".home/origin3/" + rel, "x\n")
        git(origin, "init", "-q")
        git(origin, "add", "-A")
        git(origin, "commit", "-q", "-m", "i")
        p = self.root / BIZ / "bekotes.json"
        d = json.loads(p.read_text())
        d["sources"].append({"name": "masodik", "kind": "repo", "path": "munka/masodik", "tiltott": ["archiv/**"]})
        p.write_text(json.dumps(d, ensure_ascii=False))
        r = bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "masodik", "--from", str(origin))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = sorted(q.relative_to(self.root / "munka/masodik").as_posix()
                       for q in (self.root / "munka/masodik").rglob("*") if q.is_file() and ".git" not in q.parts)
        self.assertEqual(files, ["ok.txt"])

    def test_refuses_non_empty_dest_and_unknown_source(self):
        r = bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "zoldag-web",
               "--from", str(self.root / ".home/origin/zoldag-web"))
        self.assertNotEqual(r.returncode, 0)
        r = bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "memoria",
               "--from", "x", "--dest", "munka/y")
        self.assertNotEqual(r.returncode, 0)

    def test_check_fails_when_the_file_is_put_back(self):
        done(self.root)
        self.assertIn("PASS tiltott-lemez", bk(self.root, "check", "--repo", ".", "--business", "zoldag").stdout)
        write(self.root, "munka/zoldag-web/ugyfelek/private.json", "{}\n")
        r = bk(self.root, "check", "--repo", ".", "--business", "zoldag")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL tiltott-lemez: zoldag-web:ugyfelek/private.json", r.stdout)


class KlonCaseSensitive(unittest.TestCase):
    """On a case-sensitive filesystem (a real one via hdiutil on macOS, if available)."""
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"].append({"name": "kis", "kind": "repo", "path": "munka/cs/kis",
                             "tiltott": ["ugyfelek/private.json", "*.jpg"]})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        self.origin = self.root / ".home/origin3"
        for f in ("Ugyfelek/Private.json", "sub/UGYFELEK/PRIVATE.JSON", "Photo.JPG", "ok.txt"):
            write(self.root, ".home/origin3/" + f, "x\n")
        git(self.origin, "init", "-q")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-q", "-m", "i")
        self.volume = _case_sensitive_volume(self)
        (self.root / "munka/cs").symlink_to(self.volume) if self.volume else (self.root / "munka/cs").mkdir()

    def test_case_variants_never_land(self):
        r = bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "kis", "--from", str(self.origin))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dest = self.root / "munka/cs/kis"
        files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")
                       if p.is_file() and ".git" not in p.relative_to(dest).parts)
        self.assertEqual(files, ["ok.txt"])
        import subprocess
        cfgval = subprocess.run(["git", "-C", str(dest), "config", "--local", "core.ignorecase"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(cfgval, "true")


def _case_sensitive_volume(test):
    """Mount a small case-sensitive APFS image (macOS); None where hdiutil is not available."""
    import subprocess
    import tempfile
    if not shutil.which("hdiutil"):
        return None
    tmp = pathlib.Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, tmp, True)
    mnt = tmp / "mnt"
    ok = subprocess.run(["hdiutil", "create", "-quiet", "-size", "16m", "-fs", "Case-sensitive APFS",
                         "-volname", "cs", str(tmp / "cs.dmg")]).returncode == 0 and \
        subprocess.run(["hdiutil", "attach", "-quiet", "-nobrowse", "-mountpoint", str(mnt),
                        str(tmp / "cs.dmg")]).returncode == 0
    if not ok:
        return None
    test.addCleanup(subprocess.run, ["hdiutil", "detach", "-quiet", "-force", str(mnt)])
    return mnt


def subprocess_ls(repo):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                          capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
