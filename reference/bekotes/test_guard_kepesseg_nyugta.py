"""Képességfa, 2. fázis: the receipts are the finder's, not the agent's. Writing one by hand
(Write, `echo >`, python -c, a split path) is always denied; the repo's own
`mentat_brain.py where` (by its resolved path) stays open; one known limit is pinned."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from test_guard_kint import KintBase

R = ".mentat/state/capability-receipts"


class ReceiptsAreTheFinders(KintBase):
    roles = False

    def test_hand_written_receipts_are_denied_every_way(self):
        target = str(self.root / R / "kamu.json")
        for tool, inp in (("Write", {"file_path": target, "content": "{}"}),
                          ("Edit", {"file_path": target, "old_string": "a", "new_string": "b"}),
                          ("Bash", {"command": "echo '{\"decision\": {}}' > %s/kamu.json" % R}),
                          ("Bash", {"command": "mkdir -p %s && cp x.json %s/" % (R, R)}),
                          ("Bash", {"command": "python3 -c \"open('%s/k.json','w').write('{}')\"" % R}),
                          ("Bash", {"command": "sed -i s/null/1/ %s/r1.json" % R}),
                          ("Bash", {"command": "rm -rf .mentat/state"}),
                          # each layer alone: the path layer sees a split string, the text rule python -c
                          ("Bash", {"command": "cd .mentat/state && echo '{}' > \"capab\"ility-receipts/k.json"}),
                          ("Bash", {"command": "printf x | tee %s/t.json" % R})):
            self.assertEqual(self.d(tool, inp), "deny", (tool, inp))

    def test_the_finder_itself_stays_open(self):
        for cmd in ('python3 .mentat/bin/mentat_brain.py where --find "tedd ki a netre"',
                    "python3 .mentat/bin/mentat_brain.py where --decide %s/x.json use --candidate web.publish" % R,
                    "python3 .mentat/bin/mentat_brain.py where --map"):
            self.assertEqual(self.bash(cmd), "allow", cmd)
        self.assertEqual(self.d("Read", {"file_path": str(self.root / R / "x.json")}), "allow")

    def test_a_finder_by_name_elsewhere_is_not_the_finder(self):  # CISO #81, 2
        cmd = "python3 /tmp/x/mentat_brain.py where --decide %s/x.json new --why sajat" % R
        self.assertEqual(self.bash(cmd), "deny")

    def test_known_limit_a_path_built_at_run_time(self):  # stays visible if it changes
        import szerep_kapu_kepesseg as k
        cmd = "python3 -c \"open('.mentat/state/' + 'capab' + 'ility-receipts/k.json', 'w')\""
        self.assertIsNone(k.touched(str(self.root), "Bash", {"command": cmd}, str(self.root)))


if __name__ == "__main__":
    unittest.main()
