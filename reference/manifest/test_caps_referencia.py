"""Képességfa as a reference (Krisz, 2026-10-24): `where --map --html` and `where --map` show two
levels apart (what the USER gets / what the agent needs), the projects in their own section, the
basics folded at the end; an opened row says where it lives, what it is for, and an example."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import re
import unittest

from _caps_base import CapsBase


class Reference(CapsBase):
    """Krisz, 2026-10-24: a friendly reference like an API page, not a graph of nodes."""

    def page(self):
        self.write("projects/lista/README.md", "# Lista\n")
        r = self.run_where("--map", "--html")
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.root / ".mentat" / "state" / "kepessegfa.html"
        self.assertIn(str(page.relative_to(self.root)), r.stdout)
        return page.read_text(encoding="utf-8")

    def section(self, html, key):
        m = re.search(r'<section id="%s".*?</section>' % key, html, re.S)
        self.assertTrue(m, key)
        return m.group(0)

    def test_one_self_contained_page_for_phone_light_and_dark(self):
        html = self.page()
        self.assertIn('name="viewport"', html)
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertIn(':root[data-theme="dark"]', html)
        self.assertRegex(html, r"<title>[^<]{3,40}</title>")
        self.assertFalse(re.search(r"<(script|link)[^>]+(src|href)=\"https?:", html))  # nothing from the net
        self.assertNotIn("<svg", html)  # no node graph any more

    def test_user_and_agent_levels_projects_apart_and_basics_folded_away(self):
        html = self.page()
        user, agent = self.section(html, "neked"), self.section(html, "agens")
        projects, basics = self.section(html, "projektek"), self.section(html, "alap")
        self.assertIn("vendégek nem látják egymást", user)  # what the USER gets, in their words
        self.assertNotIn("engine.core", user)
        self.assertIn("engine.core", agent)
        self.assertIn("own.project.lista", projects)
        self.assertNotIn("own.project", user + agent)
        self.assertIn("brain.mv", basics)
        self.assertNotIn("brain.mv", user + agent)
        self.assertRegex(basics, r'<details class="alap">')  # folded, at the end
        self.assertLess(html.index('id="agens"'), html.index('id="alap"'))

    def test_opened_row_says_where_it_lives_what_for_and_an_example(self):
        html = self.page()
        row = re.search(r'<details class="row" id="engine.cases">.*?</details>', html, re.S).group(0)
        self.assertIn("anytime_cases", row)  # where it is defined
        self.assertIn("Mondd például", row)  # an example in the USER's words
        agent_row = re.search(r'<details class="row" id="web.check">.*?</details>', html, re.S).group(0)
        self.assertIn("reference/manifest/mentat_web.py", agent_row)
        self.assertIn("mentat_web.py check", agent_row)  # entry as the example

    def test_the_mece_groups_in_the_websites_order(self):  # Krisz, 2026-10-24
        html = self.page()
        user = self.section(html, "neked")
        heads = re.findall(r'<h3 class="grp">([^<]+)</h3>', user)
        order = ["Memória és tudás", "Proaktivitás és ütemezés", "Munkavégzés és projektek",
                 "Kapcsolat a külvilággal", "Biztonság és kontroll", "Működés és rugalmasság"]
        self.assertEqual(heads, [h for h in order if h in heads])  # in order, none twice
        self.assertGreaterEqual(len(heads), 5)
        self.assertIn("Proaktivitás és ütemezés", self.section(html, "agens"))  # the agent side, under the same

    def test_the_markdown_follows_the_same_structure(self):
        self.write("projects/lista/README.md", "# Lista\n")
        out = self.run_where("--map").stdout
        heads = [ln for ln in out.splitlines() if ln.startswith("## ")]
        self.assertEqual(len(heads), 4, heads)
        self.assertLess(out.index("| google.calendar |"), out.index("| engine.core |"))
        self.assertLess(out.index("| engine.core |"), out.index("| own.project.lista |"))
        self.assertLess(out.index("| own.project.lista |"), out.index("| brain.mv |"))


if __name__ == "__main__":
    unittest.main()
