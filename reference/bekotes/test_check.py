"""check: PASS/FAIL per line on the vendored copy; BEKOTES.{hu,en}.md shape."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import shutil
import tempfile
import unittest

from _bekotes_repo import BIZ, HERE, bk, commit_all, done, fill_map, leltar, make_agent, szerepek, \
    vendor, vendor_list, write


class Doc(unittest.TestCase):
    def test_procedure_short_and_same_tool_list(self):
        for lang in ("hu", "en"):
            self.assertLessEqual(len((HERE / ("BEKOTES.%s.md" % lang)).read_text().splitlines()), 90)
        self.assertEqual(vendor_list("hu"), vendor_list("en"))
        shipped = {"bekotes/" + p.name for p in HERE.glob("*.py") if not p.name.startswith(("test_", "_"))}
        self.assertTrue(shipped <= set(vendor_list("hu")), shipped - set(vendor_list("hu")))

    def test_step0_local_tree_copies_the_same_set_in_both_languages(self):
        got = []
        for lang in ("hu", "en"):
            root = pathlib.Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, root, True)
            vendor(root, lang)
            got.append(sorted(p.relative_to(root).as_posix() for p in (root / ".mentat").rglob("*")
                              if p.is_file()))
        want = sorted([".mentat/bin/bekotes/" + f.split("/", 1)[1] for f in vendor_list("hu")]
                      + [".mentat/bin/" + f.split("/")[-1] for f in vendor_list("hu") if "/mentat_" in f])
        self.assertEqual(got[0], want)
        self.assertEqual(got[1], want)

    def test_procedure_states_preconditions_and_read_rule(self):
        hu = (HERE / "BEKOTES.hu.md").read_text()
        for s in ("mentat.json megvan (init-brain)", 'BK="python3 .mentat/bin/bekotes/bekotes.py"',
                  "CSAK `$BK olvas`"):
            self.assertIn(s, hu)


class Check(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)

    def check(self):
        return bk(self.root, "check", "--repo", ".", "--business", "zoldag")

    def test_empty_map_fails_every_missing_file(self):
        self.assertEqual(leltar(self.root).returncode, 0)
        self.assertEqual(szerepek(self.root).returncode, 0)
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        for name in ("terkep", "business", "rendszerek", "emberek"):
            self.assertIn("FAIL %s" % name, r.stdout)
        self.assertIn("PASS hook", r.stdout)

    def test_cited_map_passes(self):
        done(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertTrue(all(x.startswith("PASS ") for x in lines), r.stdout)
        for name in ("bekotes-json", "leltar-json", "hianylista", "hivatkozas", "szerepek",
                     "szuro", "tiltott", "hook"):
            self.assertIn("PASS %s" % name, r.stdout)

    def test_bad_citations_fail(self):
        done(self.root)
        fill_map(self.root, {"terkep.md": "- x (forrás: ismeretlen:a.md)\n- y (forrás: zoldag-web:nincs.md)\n"
                                          "- z (forrás: linear:ZOL-99)\n- m (forrás: memoria:nincs.md)\n"})
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        line = next(x for x in r.stdout.splitlines() if x.startswith("FAIL hivatkozas"))
        for s in ("ismeretlen:a.md", "zoldag-web:nincs.md", "linear:ZOL-99", "memoria:nincs.md"):
            self.assertIn(s, line)

    def test_personal_data_in_git_fails_szuro(self):
        done(self.root)
        write(self.root, BIZ + "/jegyzet.md", "írj: anna@example.com\n")
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL szuro: %s/jegyzet.md" % BIZ, r.stdout)
        self.assertNotIn("anna@", r.stdout)

    def test_szuro_also_reads_history_of_the_binding(self):
        done(self.root)
        write(self.root, BIZ + "/jegyzet.md", "írj: anna@example.com\n")
        commit_all(self.root)
        write(self.root, BIZ + "/jegyzet.md", "kitörölve\n")
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("történet:%s/jegyzet.md" % BIZ, r.stdout)

    def test_szuro_ignores_files_the_binding_does_not_write(self):
        write(self.root, "README.md", "Co-Authored-By: noreply@example.org\n")
        write(self.root, "AGENTS.md", "# Ágens\n\ncommit: noreply@example.org\n")
        done(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_blocked_source_without_reason_fails_hianylista(self):
        done(self.root)
        p = self.root / BIZ / "leltar.json"
        d = json.loads(p.read_text())
        d["sources"][0]["state"] = "blokkolt"
        d["hianylista"] = []
        p.write_text(json.dumps(d))
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL hianylista: %s" % d["sources"][0]["name"], r.stdout)

    def test_memory_citation_needs_the_approved_extract(self):
        done(self.root)
        write(self.root, "munka/regi-memoria/csak-forras.md", "x\n")
        fill_map(self.root, {"terkep.md": "- x (forrás: memoria:csak-forras.md)\n"})
        commit_all(self.root)
        r = self.check()
        self.assertIn("FAIL hivatkozas: memoria:csak-forras.md", r.stdout)

    def test_missing_hook_fails(self):
        done(self.root)
        (self.root / ".claude/settings.json").unlink()
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL hook", r.stdout)

    def test_kiado_default_with_release_agent_fails(self):
        done(self.root)
        p = self.root / BIZ / "leltar.json"
        p.write_text(json.dumps(dict(json.loads(p.read_text()), kiado_alapnak=False)))
        m = json.loads((self.root / "mentat.json").read_text())
        m["roles"] = {"default": "kiado", "installed": ["kiado"]}
        (self.root / "mentat.json").write_text(json.dumps(m))
        write(self.root, "agy/szerepek/kiado.md", "x\n")
        commit_all(self.root)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL szerepek", r.stdout)


if __name__ == "__main__":
    unittest.main()
