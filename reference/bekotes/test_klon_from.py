"""klon --from validation, and nothing of `from` (credentials) ever echoed."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import shutil
import unittest

from _bekotes_repo import BIZ, bk, make_agent, write


class KlonFrom(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)

    def klon(self, src, dest="munka/uj"):
        return bk(self.root, "klon", "--config", BIZ + "/bekotes.json", "--name", "zoldag-web",
                  "--from=" + src, "--dest", dest)

    def test_dangerous_or_unknown_forms_rejected_without_echo(self):
        for src in ("-uhack", "--upload-pack=touch x", "ext::sh -c touch% x", "fd::3", "file:///tmp/x",
                    "http://example.com/x.git", "git@-oProxyCommand=x:y", "nincs/ilyen/mappa"):
            r = self.klon(src)
            self.assertEqual(r.returncode, 1, src)
            self.assertIn("érvénytelen --from", r.stderr, src)
            self.assertNotIn(src, r.stdout + r.stderr, src)
        self.assertFalse((self.root / "munka/uj").exists())
        self.assertFalse((self.root / "x").exists())

    def test_home_relative_local_from_and_no_dotdot(self):
        r = self.klon("~/origin/zoldag-web")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.root / "munka/uj/README.md").is_file())
        r = self.klon("../%s/.home/origin/zoldag-web" % self.root.name, dest="munka/uj2")  # exists, but climbs
        self.assertEqual(r.returncode, 1)
        self.assertIn("~/", r.stderr)

    def test_credentials_never_echoed_on_git_error(self):
        r = self.klon("https://bob:tok3n@127.0.0.1:9/x.git")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("tok3n", r.stdout + r.stderr)
        self.assertNotIn("bob", r.stdout + r.stderr)

    def test_elokeszit_reports_bad_from_without_echo(self):
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"].append({"name": "rossz", "kind": "repo", "path": "munka/rossz",
                             "from": "https://bob:tok3n@127.0.0.1:9/x.git"})
        d["sources"].append({"name": "mem2", "kind": "memory", "path": "munka/nincs-memoria"})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        write(self.root, "munka/regi-memoria/bob@example.com.md", "---\ndescription: d\n---\nx\n")
        r = bk(self.root, "elokeszit", "--business", "zoldag")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("klón hiba: rossz", r.stdout)
        self.assertNotIn("tok3n", r.stdout + r.stderr)
        self.assertIn("mem2 (memory): blokkolt", r.stdout)
        self.assertNotIn("Memória-jóváhagyás (mem2)", r.stdout)
        self.assertFalse((self.root / ".bekotes/stage/mem2").exists())
        self.assertNotIn("bob@", r.stdout)
        self.assertRegex(r.stdout, r"email-[0-9a-f]{4}\.md")
        self.assertNotIn("<email>", r.stdout)


if __name__ == "__main__":
    unittest.main()
