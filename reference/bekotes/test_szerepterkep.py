"""The role map (reference/szerepek.hu.md, reference/roles.md) and the role templates agree.

SZ-X1: every template role is in both catalogs; the test IDs are the same, unique set in both.
SZ-X2: every template has a non-empty role self-image before its limits, and the release
agent's is the owner's wording. The diagram exists, is linked and has a dark-mode style.
SZ-X4: both catalogs, the diagram and the README name the six standard roles in the owner's order,
the personal assistant is their sum, and no expert persona ships as a role.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import re
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent
DOCS = {"hu": REF / "szerepek.hu.md", "en": REF / "roles.md"}
SVG = REF.parent / "assets" / "szerepterkep.svg"
HEAD = {"hu": ("## Szerep önkép", "## Korlátok"), "en": ("## Role self-image", "## Limits")}
OWNER = {"hu": ("a kódbázis gazdája és senior mérnöke", "product manager ágensen keresztül"),
         "en": ("owner and senior engineer of the codebase", "through the product manager agent")}
ID = re.compile(r"^\| (SZ-[A-Z]\d+) \|", re.M)
SIX = {"hu": ["Asszisztens", "Fejlesztő", "Consultant", "Product Manager", "Kiadó ágens", "Flottamenedzser"],
       "en": ["Assistant", "Developer", "Consultant", "Product Manager", "Release agent", "Fleet manager"]}
SUM = {"hu": "### Személyi asszisztens (a hat szerep összege", "en": "### Personal assistant (the sum of the six roles"}
README = {"hu": REF.parent / "README.hu.md", "en": REF.parent / "README.md"}
STANDARD = re.compile(r"^### (\d)\. (.+)$", re.M)
PERSONA = re.compile(r"ciso|champion", re.I)


def roles():
    return sorted({p.name.split(".")[0] for p in (HERE / "szerepek").glob("*.md")})


def self_image(text, lang):
    head, limits = HEAD[lang]
    start, end = text.find(head), text.find(limits)
    return text[start + len(head):end].strip() if -1 < start < end else ""


class RoleMap(unittest.TestCase):
    def test_every_template_role_is_in_both_catalogs(self):
        self.assertTrue(roles())
        for lang, doc in DOCS.items():
            text = doc.read_text(encoding="utf-8")
            for name in roles():
                self.assertIn("| `%s` |" % name, text, "%s missing from %s" % (name, doc.name))

    def test_test_ids_are_unique_and_the_same_in_both_languages(self):
        ids = {}
        for lang, doc in DOCS.items():
            found = ID.findall(doc.read_text(encoding="utf-8"))
            self.assertEqual(len(found), len(set(found)), "duplicate ID in %s" % doc.name)
            ids[lang] = set(found)
        self.assertEqual(ids["hu"], ids["en"])

    def test_every_template_has_a_self_image_before_its_limits(self):
        for name in roles():
            for lang in ("hu", "en"):
                text = (HERE / "szerepek" / ("%s.%s.md" % (name, lang))).read_text(encoding="utf-8")
                self.assertGreater(len(self_image(text, lang)), 200, "%s.%s" % (name, lang))

    def test_the_release_agent_self_image_is_the_owners_wording(self):
        for lang, phrases in OWNER.items():
            got = self_image((HERE / "szerepek" / ("kiado.%s.md" % lang)).read_text(encoding="utf-8"), lang)
            for p in phrases:
                self.assertIn(p, got)

    def test_the_diagram_is_linked_and_themed(self):
        svg = SVG.read_text(encoding="utf-8")
        self.assertIn("<title", svg)
        self.assertIn("prefers-color-scheme: dark", svg)
        self.assertNotRegex(svg, r'fill="(#fff|#ffffff|white)"')
        for doc in DOCS.values():
            self.assertIn("../assets/szerepterkep.svg", doc.read_text(encoding="utf-8"))

    def test_the_six_standard_roles_are_in_the_owners_order(self):
        for lang, doc in DOCS.items():
            text = doc.read_text(encoding="utf-8")
            found = STANDARD.findall(text)
            self.assertEqual([n for n, _ in found], ["1", "2", "3", "4", "5", "6"], doc.name)
            self.assertEqual([name for _, name in found], SIX[lang], doc.name)
            self.assertIn(SUM[lang], text)
            self.assertLess(text.find("### 6. "), text.find(SUM[lang]), "the sum comes after the six")
        svg = SVG.read_text(encoding="utf-8")
        at = [svg.find("%d · %s" % (i + 1, name)) for i, name in enumerate(SIX["hu"])]
        self.assertNotIn(-1, at, "a standard role is missing from the diagram")
        self.assertIn("Személyi asszisztens", svg)

    def test_no_expert_persona_ships_as_a_role(self):
        shipped = list(DOCS.values()) + [SVG] + sorted((HERE / "szerepek").glob("*.md"))
        for p in shipped:
            self.assertNotRegex(p.read_text(encoding="utf-8"), PERSONA, p.name)

    def test_the_readme_names_the_same_six_roles(self):
        for lang, readme in README.items():
            text = readme.read_text(encoding="utf-8").lower()
            for name in SIX[lang]:
                self.assertIn(name.lower(), text, "%s missing from %s" % (name, readme.name))


if __name__ == "__main__":
    unittest.main()
