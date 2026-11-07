"""Citations as agents really write them; `~/` local sources leave no home path in git."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import shutil
import unittest

from _bekotes_repo import BIZ, bk, commit_all, done, fill_map, make_agent, write


class Citations(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        write(self.root, ".home/bank/befizetesek.csv", "datum;osszeg\n")
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"][0]["from"] = "~/origin/zoldag-web"
        d["sources"].append({"name": "bank", "kind": "live", "path": "~/bank/befizetesek.csv"})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        done(self.root)

    def check(self, terkep):
        fill_map(self.root, {"terkep.md": terkep})
        commit_all(self.root)
        return bk(self.root, "check", "--repo", ".", "--business", "zoldag").stdout

    def test_several_citations_in_one_parenthesis(self):
        # bank is restricted for fejleszto (test_korlatozott), so the parsing cases use linear
        out = self.check("- a (forrás: zoldag-web:README.md, linear:ZOL-1)\n"
                         "- b (forrás: linear:ZOL-1; zoldag-web:docs/a.md)\n"
                         "- c (forrás: linear:ZOL-1, 2026-10-17 18:00)\n")
        self.assertIn("PASS hivatkozas", out)
        self.assertIn("PASS szuro", out)  # "~/..." in bekotes.json is no home path

    def test_live_citation_needs_the_file_name_and_ranges_are_not_ids(self):
        out = self.check("- a (forrás: bank:masik.csv)\n- b (forrás: linear:ZOL-1…ZOL-3)\n"
                         "- c (forrás: zoldag-web:README.md, linear:ZOL-99)\n")
        line = next(x for x in out.splitlines() if x.startswith("FAIL hivatkozas"))
        for s in ("bank:masik.csv", "linear:ZOL-1…ZOL-3", "linear:ZOL-99"):
            self.assertIn(s, line)
        self.assertNotIn("zoldag-web:README.md", line)


if __name__ == "__main__":
    unittest.main()
