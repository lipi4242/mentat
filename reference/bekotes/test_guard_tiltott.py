"""Guard: forbidden reads (tiltott globs, secret names) and Grep/Glob over their ancestors."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import shutil
import subprocess
import sys
import unittest

from _bekotes_repo import BIZ, env, make_agent, szerepek


class GuardTiltott(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"].append({"name": "w", "kind": "repo", "path": "munka/w", "tiltott": ["**/*.jpg"]})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        self.assertEqual(szerepek(self.root).returncode, 0)

    def decide(self, tool, inp, role=None, cwd=None):
        e = dict(env(self.root), CLAUDE_PROJECT_DIR=str(self.root))
        if role:
            e["MENTAT_ROLE"] = role
        payload = {"session_id": "s-%s" % (role or "x"), "cwd": str(cwd or self.root),
                   "tool_name": tool, "tool_input": inp}
        r = subprocess.run([sys.executable, str(self.root / ".mentat/bin/bekotes/szerep_guard.py")],
                           input=json.dumps(payload), capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else "allow"

    def test_double_star_glob_matches_at_the_source_root(self):
        self.assertEqual(self.decide("Read", {"file_path": "munka/w/p.jpg"}), "deny")
        self.assertEqual(self.decide("Read", {"file_path": "munka/w/a/b/p.jpg"}), "deny")
        self.assertEqual(self.decide("Read", {"file_path": "munka/w/p.txt"}), "allow")

    def test_secret_names_denied_in_sources_except_for_the_developer(self):
        for p in ("munka/zoldag-web/.env", "munka/zoldag-web/cfg/deploy.pem", "munka/w/id_rsa",
                  "munka/regi-memoria/.npmrc"):
            self.assertEqual(self.decide("Read", {"file_path": p}), "deny", p)
            # the developer may, but a secret file's content needs the USER (szerep_kapu "titok")
            self.assertEqual(self.decide("Read", {"file_path": p}, "fejleszto"), "ask", p)
        self.assertEqual(self.decide("Read", {"file_path": "agy/.env.example"}), "ask")

    def test_grep_over_an_ancestor_of_a_forbidden_location(self):
        for inp in ({"pattern": "x", "path": "munka/zoldag-web"}, {"pattern": "x", "path": "munka"},
                    {"pattern": "x", "path": str(self.root / "munka/zoldag-web/ugyfelek")},
                    {"pattern": "x"}):
            self.assertEqual(self.decide("Grep", inp), "deny", inp)
            self.assertEqual(self.decide("Grep", inp, "fejleszto"), "allow", inp)
        self.assertEqual(self.decide("Glob", {"pattern": "*", "path": "munka/zoldag-web"}), "deny")
        self.assertEqual(self.decide("Grep", {"pattern": "x", "path": "munka/zoldag-web/docs"}), "allow")
        self.assertEqual(self.decide("Grep", {"pattern": "x", "path": "agy"}), "allow")
        self.assertEqual(self.decide("Grep", {"pattern": "x"}, cwd=self.root / "agy"), "allow")


if __name__ == "__main__":
    unittest.main()
