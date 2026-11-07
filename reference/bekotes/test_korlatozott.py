"""A role-restricted source's facts stay out of the shared map (h1-16 after K28).

The developer could not read the bank CSV any more, but quoted its amounts from
terkep.md, where the onboarding had written them with `(forrás: bank:…)`. The
state rule: a citation of a source that an installed role may not Read never
appears in the shared map files; such facts go under <biz>/<denied folder>/,
which the same Read deny already covers.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import shutil
import unittest

from _bekotes_repo import BIZ, bk, commit_all, done, fill_map, make_agent, write
from test_guard import GuardBase


class SharedMap(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        write(self.root, ".home/bank/befizetesek.csv", "datum;osszeg\n")
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"].append({"name": "bank", "kind": "live", "path": "~/bank/befizetesek.csv"})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        done(self.root)  # installs fejleszto: Read(**/bank/**)

    def check(self, files):
        fill_map(self.root, files)
        commit_all(self.root)
        return bk(self.root, "check", "--repo", ".", "--business", "zoldag").stdout

    def test_restricted_citation_on_the_shared_map_fails(self):
        out = self.check({"terkep.md": "- Két eltérés a befizetésekben (forrás: bank:befizetesek.csv)\n"
                                       "- Web (forrás: zoldag-web:README.md)\n"})
        line = next(x for x in out.splitlines() if x.startswith("FAIL hivatkozas"))
        self.assertIn("bank:befizetesek.csv", line)
        self.assertIn("bank/", line)  # says where the fact belongs
        self.assertNotIn("zoldag-web:README.md", line)

    def test_restricted_facts_in_their_own_folder_pass(self):
        write(self.root, BIZ + "/bank/befizetesek.md",
              "- Két eltérés a befizetésekben (forrás: bank:befizetesek.csv)\n")
        out = self.check({"terkep.md": "- Banki eltérések: `bank/befizetesek.md`\n"
                                       "- Web (forrás: zoldag-web:README.md)\n"})
        self.assertIn("PASS hivatkozas", out)


class RestrictedFolderIsDenied(GuardBase):
    def test_developer_cannot_read_the_restricted_folder(self):
        p = "agy/business/zoldag/bank/befizetesek.md"
        self.assertEqual(self.decide("Read", {"file_path": p}, "fejleszto"), "deny")
        self.assertEqual(self.decide("Bash", {"command": "cat " + p}, "fejleszto"), "deny")
        self.assertEqual(self.decide("Read", {"file_path": p}, "asszisztens", sid="s2"), "allow")


if __name__ == "__main__":
    unittest.main()
