"""The brain's six skills live in the repo (.claude/skills/<name>/SKILL.md), in the USER's language:
downloaded once with the tools, installed without the network, never overwritten silently."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
RELEASE = HERE.parent.parent
sys.path.insert(0, str(HERE))
import mentat_verify  # noqa: E402

SIX = ("develop", "subagent", "status", "backlog", "model", "bug-report")


def installed_bin(lang):
    """A .mentat/bin/ as the curl step leaves it: the tools plus skills/<name>/SKILL.<lang>.md."""
    root = pathlib.Path(tempfile.mkdtemp())
    bin_dir = root / ".mentat" / "bin"
    shutil.copytree(HERE, bin_dir, ignore=shutil.ignore_patterns("test_*", "__pycache__"))
    shutil.copytree(HERE.parent / "bekotes", bin_dir / "bekotes", ignore=shutil.ignore_patterns("test_*", "__pycache__"))
    for name in SIX:
        (bin_dir / "skills" / name).mkdir(parents=True)
        shutil.copy(RELEASE / "skills" / name / ("SKILL.%s.md" % lang), bin_dir / "skills" / name)
    return root, bin_dir


class NoNetwork:
    def __enter__(self):
        self.real = socket.socket.connect
        socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(OSError("network is off in this test"))

    def __exit__(self, *exc):
        socket.socket.connect = self.real


class Download(unittest.TestCase):
    def test_the_curl_step_downloads_the_six_skills_in_both_languages(self):
        for doc, lang in (("initialization.md", "en"), ("initialization.hu.md", "hu")):
            got = dict(mentat_verify.listing((RELEASE / "reference" / doc).read_text(encoding="utf-8")))
            for name in SIX:
                self.assertEqual(got.get("skills/%s/SKILL.%s.md" % (name, lang)),
                                 "skills/%s/SKILL.%s.md" % (name, lang), doc)

    def test_agents_template_names_the_local_skill_not_a_download(self):
        for lang in ("en", "hu"):
            text = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertNotIn("skills/develop/SKILL.{LANG}.md", text)
            self.assertIn("the `develop` skill." if lang == "en" else "a `develop` skill.", text)


class Install(unittest.TestCase):
    def setUp(self):
        self.root, self.bin = installed_bin("hu")
        sys.path.insert(0, str(self.bin))
        import mentat_skills
        self.skills = mentat_skills

    def tearDown(self):
        sys.path.remove(str(self.bin))
        sys.modules.pop("mentat_skills", None)

    def dst(self, name):
        return self.root / ".claude" / "skills" / name / "SKILL.md"

    def test_installs_the_six_in_the_users_language_without_the_network(self):
        with NoNetwork():
            log = self.skills.install(self.root, "hu", self.bin / "skills")
        for name in SIX:
            self.assertEqual(self.dst(name).read_text(encoding="utf-8"),
                             (RELEASE / "skills" / name / "SKILL.hu.md").read_text(encoding="utf-8"), name)
        self.assertEqual(len([l for l in log if ".claude/skills/" in l]), 6)
        self.assertEqual(self.skills.missing(self.root), [])

    def test_a_new_release_replaces_an_untouched_skill(self):
        self.skills.install(self.root, "hu", self.bin / "skills")
        new = self.bin / "skills" / "status" / "SKILL.hu.md"
        new.write_text(new.read_text(encoding="utf-8") + "\nÚj lépés.\n", encoding="utf-8")
        log = self.skills.install(self.root, "hu", self.bin / "skills")
        self.assertTrue(self.dst("status").read_text(encoding="utf-8").endswith("Új lépés.\n"))
        self.assertTrue(any("status" in l for l in log))

    def test_a_hand_edited_skill_is_kept_and_the_difference_is_named(self):
        self.skills.install(self.root, "hu", self.bin / "skills")
        mine = self.dst("develop").read_text(encoding="utf-8") + "\nA saját szabályom.\n"
        self.dst("develop").write_text(mine, encoding="utf-8")
        new = self.bin / "skills" / "develop" / "SKILL.hu.md"
        new.write_text(new.read_text(encoding="utf-8") + "\nÚj lépés.\n", encoding="utf-8")
        log = self.skills.install(self.root, "hu", self.bin / "skills")
        self.assertEqual(self.dst("develop").read_text(encoding="utf-8"), mine)
        said = [l for l in log if "develop" in l]
        self.assertEqual(len(said), 1, log)
        self.assertIn("diff", said[0])
        self.assertIn(str(new), said[0])
        self.assertEqual(self.skills.install(self.root, "hu", self.bin / "skills"), said)   # said again, still kept


class Scaffold(unittest.TestCase):
    def test_fresh_install_has_the_six_and_the_check_is_green(self):
        root, bin_dir = installed_bin("en")
        home = tempfile.mkdtemp()
        env = {"HOME": home, "PATH": "/usr/bin:/bin:/usr/local/bin", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": home + "/gitconfig"}
        run = lambda *a: subprocess.run([sys.executable, "-I", str(bin_dir / "mentat_scaffold.py"), "--lang", "en",
                                         "--repo", str(root), *a], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        r = run("--base", "https://example.com/kit/v9.9.9/")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in SIX:
            self.assertTrue((root / ".claude" / "skills" / name / "SKILL.md").is_file(), name)
        sys.path.insert(0, str(bin_dir))
        try:
            import mentat_scaffold
            own = mentat_scaffold.own_files(root, "en")
        finally:
            sys.path.remove(str(bin_dir))
            sys.modules.pop("mentat_scaffold", None)
        self.assertIn(".claude/skills/develop/SKILL.md", own)
        (root / ".claude" / "skills" / "model" / "SKILL.md").unlink()
        r = run("--check")
        self.assertIn("skills/model", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
