"""olvas grep|show: targeted reads over the business sources, never a forbidden path."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import shutil
import unittest

from _bekotes_repo import BIZ, bk, git, make_agent, write


class Olvas(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        write(self.root, "munka/zoldag-web/ugyfelek/private.json", '{"KAKUKK": 1}\n')
        write(self.root, "munka/zoldag-web/src/app.js", "// KAKUKK nyilvános\n")
        write(self.root, "munka/zoldag-web/node_modules/x/i.js", "KAKUKK\n")
        web = self.root / "munka/zoldag-web"
        git(web, "add", "--sparse", "-f", "-A")  # sparse clone
        git(web, "commit", "-q", "-m", "fixture")

    def olvas(self, *a):
        return bk(self.root, "olvas", *a)

    def test_grep_skips_forbidden_and_excluded(self):
        r = self.olvas("grep", "KAKUKK")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("zoldag-web:src/app.js:1:", r.stdout)
        self.assertNotIn("private.json", r.stdout)
        self.assertNotIn("node_modules", r.stdout)

    def test_grep_one_source(self):
        r = self.olvas("grep", "domain", "--source", "memoria")
        self.assertIn("memoria:projekt-domain.md:2:", r.stdout)
        self.assertNotIn("zoldag-web", self.olvas("grep", "KAKUKK", "--source", "memoria").stdout)

    def test_show_reads_allowed_and_refuses_forbidden(self):
        r = self.olvas("show", "zoldag-web:README.md")
        self.assertEqual((r.returncode, r.stdout), (0, "# Zöldág web\n"))
        r = self.olvas("show", "zoldag-web:ugyfelek/private.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tiltott", r.stderr)
        self.assertNotIn("KAKUKK", r.stdout + r.stderr)
        self.assertEqual(self.olvas("show", "zoldag-web:../../mentat.json").returncode, 1)

    def test_show_path_tricks_are_refused(self):
        web = self.root / "munka/zoldag-web"
        (web / "lnk").symlink_to("ugyfelek", target_is_directory=True)
        (web / "kint").symlink_to(self.root / BIZ, target_is_directory=True)
        for ref in ("ugyfelek//private.json", "ugyfelek/./private.json",
                    "UGYFELEK/private.json", "Ugyfelek/PRIVATE.json",
                    "lnk/private.json", "kint/bekotes.json", "./README.md", "ugyfelek/"):
            r = self.olvas("show", "zoldag-web:" + ref)
            self.assertEqual(r.returncode, 1, ref)
            self.assertNotIn("KAKUKK", r.stdout + r.stderr, ref)
            self.assertNotIn("sources", r.stdout, ref)

    def test_untracked_and_secret_files_are_never_read(self):
        web = self.root / "munka/zoldag-web"
        write(self.root, "munka/zoldag-web/.env", "TITOK=KAKUKK\n")          # untracked
        write(self.root, "munka/zoldag-web/src/uj.js", "KAKUKK uj\n")        # untracked
        for name in ("deploy.pem", "x.key", "id_ed25519", ".npmrc", "credentials.json", ".env.prod"):
            write(self.root, "munka/zoldag-web/cfg/" + name, "KAKUKK\n")
        git(web, "add", "--sparse", "-f", "cfg")
        git(web, "commit", "-q", "-m", "cfg")
        write(self.root, BIZ + "/memoria/.env", "KAKUKK\n")
        out = self.olvas("grep", "KAKUKK").stdout
        self.assertNotIn("uj.js", out)
        self.assertNotIn(".env", out)
        self.assertNotIn("cfg/", out)
        for ref in ("zoldag-web:.env", "zoldag-web:src/uj.js", "zoldag-web:cfg/deploy.pem",
                    "zoldag-web:cfg/.npmrc", "memoria:.env"):
            r = self.olvas("show", ref)
            self.assertEqual(r.returncode, 1, ref)
            self.assertNotIn("KAKUKK", r.stdout + r.stderr, ref)

    def test_grep_does_not_follow_symlinked_dirs(self):
        (self.root / "munka/zoldag-web/lnk").symlink_to("ugyfelek", target_is_directory=True)
        r = self.olvas("grep", "KAKUKK")
        self.assertNotIn("lnk/", r.stdout)
        self.assertNotIn("private.json", r.stdout)


if __name__ == "__main__":
    unittest.main()
