"""K23 (h2 measurement 2026-10-19, h2-5..7 = 1): putting the work on the web
for a non-technical user. The agent opened a quick tunnel from the laptop with
its own password, printed the password in the chat, and claimed Cloudflare
needs a domain. The always-loaded rule names the base path and the bans; the
screen-by-screen steps live in a reference file read only when needed.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent
TOOL = HERE / "mentat_scaffold.py"
RULE = {
    "hu": ["Netre kitétel", "workers.dev", "domain nem kell", "Cloudflare Access",
           "alagút", "VPN", "saját jelszó", "titkot ne írj", "reference/publish-web.hu.md"],
    "en": ["Putting it on the web", "workers.dev", "no domain needed", "Cloudflare Access",
           "tunnel", "VPN", "own password", "never print a secret", "reference/publish-web.md"],
}
BANS = ["trycloudflare", "ngrok", "Tailscale Funnel/Serve", "VPN", "Workers Scripts",
        "Account Settings · Read", "workers.dev"]
STEPS = {
    "publish-web.hu.md": ["Domain nem kell", "kitétele a netre", "a chatben", "My Profile", "API Tokens", "Edit Cloudflare Workers", "D1", "Edit",
                          "10000", "0600", "mentat_cf_access.py", "migr"],
    "publish-web.md": ["No domain is needed", "exposing that machine", "in the chat", "My Profile", "API Tokens", "Edit Cloudflare Workers", "D1", "Edit",
                       "10000", "0600", "mentat_cf_access.py", "migrat"],
}


class PublishWeb(unittest.TestCase):
    def agents(self, lang):
        root = pathlib.Path(tempfile.mkdtemp())
        home = tempfile.mkdtemp()
        env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))
        r = subprocess.run([sys.executable, str(TOOL), "--lang", lang, "--repo", str(root),
                            "--base", "https://example.com/kit/v9.9.9/"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (root / "AGENTS.md").read_text(encoding="utf-8")
        return text[text.find("<!-- mentat:managed:start intake -->"):
                    text.find("<!-- mentat:managed:end intake -->")]

    def test_always_loaded_rule_names_the_path_and_the_bans(self):
        for lang, phrases in RULE.items():
            block = self.agents(lang)
            for p in phrases:
                self.assertIn(p, block, "%s: %s" % (lang, p))

    def test_import_is_reconciled_and_checked_as_the_user(self):
        """h2-5/6 (0.3.0): rows dropped by filtering on import; the first deploy answered 403
        behind Access and was called done. The whole cleaned list goes up, the count and the
        dropped/merged items are agreed first, and the result is tried as the USER."""
        want = {"publish-web.hu.md": ["a teljes", "állapot", "nem szűrés", "hány tétel", "kimaradt",
                                      "összevon", "a FELHASZNÁLÓ szemével", "bejelentkez", "csak utána"],
                "publish-web.md": ["the whole", "status", "not a filter", "how many items", "left out",
                                   "merged", "as the USER", "signed-in", "only then"]}
        for name, phrases in want.items():
            text = (REF / name).read_text(encoding="utf-8")
            for p in phrases:
                self.assertIn(p, text, "%s: %s" % (name, p))

    def test_access_follows_todays_screens_and_no_invented_header_check(self):
        """h2-5 (0.3.0, both models): the steps named buttons that were not there, and the
        worker rejected requests without a hand-checked Access header: 403 after deploy.
        The steps follow today's dashboard (Cloudflare docs, Workers > Cloudflare Access),
        the worker does not invent an Access check, and a signed-in request is tried first."""
        # Since the API tool (mentat_cf_access.py) the protection is a command, not button names.
        want = {"publish-web.hu.md": ["Access", "mentat_cf_access.py ensure", "Access: Apps and Policies",
                                      "ctx.access", "POLICY_AUD", "TEAM_DOMAIN", "403", "CF_Authorization",
                                      "lesítés előtt"],
                "publish-web.md": ["Access", "mentat_cf_access.py ensure", "Access: Apps and Policies",
                                   "ctx.access", "POLICY_AUD", "TEAM_DOMAIN", "403", "CF_Authorization",
                                   "efore calling it live"]}
        for name, phrases in want.items():
            text = (REF / name).read_text(encoding="utf-8")
            for p in phrases:
                self.assertIn(p, text, "%s: %s" % (name, p))
            self.assertNotIn("rejects a request without a `Cf-Access-Jwt-Assertion`", text, name)
            self.assertNotIn("utasítsa el a kérést, ha nincs `Cf-Access-Jwt-Assertion`", text, name)

    def test_deploy_only_on_request_and_done_says_where(self):
        """h2-6 (0.3.0): deployed without being asked. Going live is the USER's call, and the
        done report says whether it is live (and where) or only local."""
        want = {"publish-web.hu.md": ["csak akkor élesíts", "kifejezett", "igen", "élesben van-e", "csak helyben"],
                "publish-web.md": ["deploy only when", "explicitly", "yes", "whether it is live", "only local"]}
        for name, phrases in want.items():
            text = (REF / name).read_text(encoding="utf-8")
            for p in phrases:
                self.assertIn(p, text, "%s: %s" % (name, p))

    def test_token_steps_are_few_at_a_time_and_follow_the_template_rows(self):
        """h2-5 (0.3.0): eight sub-steps in one message, and a new permission row where the
        template already had one at Read. One or two steps per message; change the
        existing row's level, add a row only if the template has none."""
        want = {"publish-web.hu.md": ["egy-két lépés", "üzenetenként", "meglévő sor", "Read → Edit", "új sort csak",
                                      "mentat_cf_token.py next", "--check"],
                "publish-web.md": ["one or two steps", "per message", "existing row", "Read → Edit", "add a row only",
                                   "mentat_cf_token.py next", "--check"]}
        for name, phrases in want.items():
            text = (REF / name).read_text(encoding="utf-8")
            for p in phrases:
                self.assertIn(p, text, "%s: %s" % (name, p))

    def test_reference_file_has_the_screens_and_is_indexed(self):
        index = (REF / "_index.md").read_text(encoding="utf-8")
        for name, phrases in STEPS.items():
            text = (REF / name).read_text(encoding="utf-8")
            for p in phrases + BANS:
                self.assertIn(p, text, "%s: %s" % (name, p))
            self.assertLess(len(text.encode("utf-8")), 5000, name)  # fetched on demand, keep it small
        self.assertIn("reference/publish-web", index)


if __name__ == "__main__":
    unittest.main()
