"""DeepSeek round (classes only): the guard's own code is not the agent's to edit; a project's
Cloudflare database setup has a named route; bounces speak the brain's language; mail goes out
only through a read-back. Each case red before its fix."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from test_guard_kint import KintBase


class DsRound(KintBase):
    roles = False

    def why(self, tool, inp, mode="bypassPermissions"):
        r = self.run_guard(self.payload(tool, inp, mode), None)
        out = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else {}
        return out.get("permissionDecision", "allow"), out.get("permissionDecisionReason", "")

    def bash(self, cmd, mode="bypassPermissions"):
        return self.why("Bash", {"command": cmd}, mode)

    def test_the_guard_and_the_product_tools_are_not_edited_by_the_agent(self):
        for tool, inp in (("Write", {"file_path": ".mentat/bin/mentat_final.py", "content": "x"}),
                          ("Edit", {"file_path": ".mentat/bin/bekotes/szerep_guard.py", "old_string": "a", "new_string": "b"}),
                          ("Bash", {"command": "python3 -c \"open('.mentat/bin/bekotes/szerep_kapu.py','w').write('')\""}),
                          ("Bash", {"command": "python3 - <<'X'\nimport pathlib; pathlib.Path('.claude/settings.json').write_text('{}')\nX"})):
            d, reason = self.why(tool, inp)
            self.assertEqual(d, "deny", inp)
            self.assertIn("telepít", reason, inp)  # the installer, with the USER's own yes
        self.assertEqual(self.bash("cp .mentat/bin/bekotes/mentat_*.py .mentat/bin/", "default")[0], "allow",
                         "the documented refresh (BEKOTES step 0) stays open")

    def test_a_cloudflare_database_setup_names_its_route(self):
        d, reason = self.bash("npx wrangler d1 create lista")
        self.assertEqual(d, "deny")
        self.assertIn("mentat_web.py deploy --approved", reason)
        self.assertEqual(self.bash("python3 .mentat/bin/mentat_web.py deploy --approved 'igen' -- npx wrangler d1 create lista")[0], "allow")

    def test_mail_goes_through_the_read_back(self):
        for cmd in ("sendmail -t < level.txt", "msmtp -t < level.txt",
                    "python3 -c \"import smtplib; s=smtplib.SMTP('smtp.x'); s.sendmail('a','b','c')\""):
            d, reason = self.bash(cmd)
            self.assertEqual(d, "deny", cmd)
            self.assertIn("mentat_final.py", reason, cmd)

    def test_an_english_brain_gets_english_bounces(self):
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["agent"] = {"name": "x", "language": "en"}
        (self.root / "mentat.json").write_text(json.dumps(doc))
        _, reason = self.bash("cat .env")
        self.assertIn("the USER", reason)
        self.assertNotIn("FELHASZNÁLÓ", reason)


    def test_every_headless_deny_names_a_route(self):
        for cmd, route in (("rm -rf ~/business/old", "munkamappán belül"),
                           ("git push --force origin main", "--force nélkül"),
                           ("HOME=/tmp python3 x.py", "környezet"),
                           ("git -c core.hooksPath=/tmp x status", "user.name"),
                           ("cat ~/business/x.txt", "nevezze meg")):
            d, reason = self.bash(cmd)
            self.assertEqual(d, "deny", cmd)
            self.assertIn(route, reason, cmd)


if __name__ == "__main__":
    unittest.main()
