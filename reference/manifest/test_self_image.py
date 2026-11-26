"""The self-image block: first in AGENTS.md, at most 600 bytes, from roles and szerep-onkep.md, --check."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import mentat_self_image as si

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://example.com/kit/v9.9.9/"
# The scaffolded AGENTS.md before the self-image block (the old "1. Identity" section), in bytes.
BEFORE = {"hu": 10143, "en": 9389}
OLD_IDENTITY = {"hu": ("## 1. Identitás", "Te: <ügynök neve TBD>", "tanácsadói menedzser szerepébe lép"),
                "en": ("## 1. Identity", "You: <agent name TBD>", "consulting manager when needed")}
MINE = {"hu": "Úgy gondolj magadra, mint a vállalkozás pénzügyi vezetője: minden számnak forrása van.",
        "en": "Think of yourself as the business's finance lead: every number has a source."}
STANDARD = {"hu": ("asszisztens: a gazda megbízható kabinetfőnöke", "- kiadó ágens: a kódbázis gazdája és senior mérnöke",
                   "Ezen kívül a következő módokon gondolok magamra:", "- penzugy: a vállalkozás pénzügyi vezetője"),
            "en": ("assistant: the owner's trusted chief of staff", "- release agent: the owner and senior engineer of "
                   "the codebase", "Besides that, I think of myself in these ways:",
                   "- penzugy: the business's finance lead")}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        self.env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))

    def tool(self, name, *args):
        return subprocess.run([sys.executable, str(HERE / name), "--repo", str(self.root), *args],
                              capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")

    def agents(self):
        return (self.root / "AGENTS.md").read_text(encoding="utf-8")

    def brain(self, lang, roles):
        root = si.ROOT[lang]
        (self.root / "mentat.json").write_text(json.dumps(
            {"agent": {"name": "Thufir", "language": lang}, "components": {"brain": {"root": root}},
             "roles": roles}), encoding="utf-8")
        (self.root / root).mkdir(exist_ok=True)
        (self.root / root / "szerep-onkep.md").write_text(
            "# x\n\n<!-- mentat:user-owned szerep-onkep szerep=penzugy alap=custom verzio=0.7.0 -->\n%s\n"
            "<!-- /mentat:user-owned -->\n" % MINE[lang], encoding="utf-8")


class Scaffolded(Base):
    def test_the_first_block_is_the_self_image_and_the_skeleton_did_not_grow(self):
        for lang in ("hu", "en"):
            with self.subTest(lang=lang):
                shutil.rmtree(self.root)
                self.root.mkdir()
                r = self.tool("mentat_scaffold.py", "--lang", lang, "--base", BASE)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                text = self.agents()
                self.assertTrue(text.startswith(si.START + "\n<!-- self-image hash="), text[:120])
                block = si.BLOCK.search(text).group(0)
                self.assertLessEqual(len(block.encode("utf-8")), si.MAX_BYTES)
                self.assertIn(si.TEXT[lang]["noname"], block)  # init fills it from mentat.json
                for gone in OLD_IDENTITY[lang]:
                    self.assertNotIn(gone, text)
                self.assertLessEqual(len(text.encode("utf-8")), BEFORE[lang])
                r = self.tool("mentat_self_image.py", "--check", "--lang", lang)  # no name yet: not a done brain
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual(r.stdout.strip(), "OPEN placeholder %s in self-image (mentat.json agent.name)"
                                 % si.TEXT[lang]["noname"])
                print("%s: %d -> %d bytes" % (lang, BEFORE[lang], len(text.encode("utf-8"))), file=sys.stderr)

    def test_the_name_comes_in_with_mentat_json(self):
        r = self.tool("mentat_scaffold.py", "--lang", "hu", "--base", BASE, "--name", "Thufir",
                      "--version", "9.9.9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.agents().startswith(si.START))
        self.assertIn("Thufir vagyok, személyi asszisztens: a gazda jobbkeze.", self.agents())
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 0)


class Render(Base):
    def test_standard_roles_from_the_template_a_custom_role_from_its_block_in_both_languages(self):
        for lang in ("hu", "en"):
            with self.subTest(lang=lang):
                self.brain(lang, {"default": "asszisztens", "installed": ["asszisztens", "kiado", "penzugy"]})
                (self.root / "AGENTS.md").write_text("# own text\n", encoding="utf-8")
                si.write(self.root)
                text = self.agents()
                self.assertTrue(text.startswith(si.START))
                for s in STANDARD[lang]:
                    self.assertIn(s, text)
                self.assertIn("@%s/szerep-onkep.md" % si.ROOT[lang], text)
                self.assertTrue(text.endswith("\n# own text\n"))

    def test_at_most_three_more_roles_and_never_over_600_bytes(self):
        self.brain("hu", {"default": "consultant", "installed": ["consultant", "fejleszto", "kiado",
                                                               "backlog-manager", "asszisztens"]})
        b = si.block(si.facts(self.root, "hu"))
        self.assertEqual(b.count("\n- "), 4)  # three roles and the "and N more" line
        self.assertIn("- és még 1: lásd az önkép-fájlt", b)
        self.assertLessEqual(len(b.encode("utf-8")), si.MAX_BYTES)
        long = self.root / "agy" / "szerep-onkep.md"
        long.write_text(long.read_text(encoding="utf-8").replace(MINE["hu"], "Úgy gondolj magadra, mint " + "nagyon " * 90 + "jó."), encoding="utf-8")
        self.brain_roles("hu", {"default": "penzugy", "installed": ["penzugy"]})
        with self.assertRaises(si.TooBig):
            si.block(si.facts(self.root, "hu"))
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 2)

    def brain_roles(self, lang, roles):
        m = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
        m["roles"] = roles
        (self.root / "mentat.json").write_text(json.dumps(m), encoding="utf-8")


class Check(Base):
    def test_green_when_unchanged_red_after_a_source_change_and_no_fleet_needed(self):
        self.brain("en", {"default": "fejleszto", "installed": ["fejleszto", "penzugy"]})
        (self.root / "AGENTS.md").write_text("## 1. The USER\n", encoding="utf-8")
        self.assertEqual(self.tool("mentat_self_image.py").returncode, 0)
        self.assertFalse(any(p.name.startswith("fleet") for p in self.root.rglob("*")))
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 0)
        onkep = self.root / "brain" / "szerep-onkep.md"
        onkep.write_text(onkep.read_text(encoding="utf-8").replace("finance lead", "finance chief"), encoding="utf-8")
        r = self.tool("mentat_self_image.py", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DRIFT", r.stdout)
        self.assertEqual(self.tool("mentat_self_image.py").returncode, 0)
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 0)
        m = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
        m["roles"]["installed"].append("kiado")
        (self.root / "mentat.json").write_text(json.dumps(m), encoding="utf-8")
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 1)

    def test_a_block_that_is_not_first_is_red_and_writing_moves_it_before_fleet_place(self):
        self.brain("hu", {"default": "asszisztens", "installed": ["asszisztens"]})
        fleet = "<!-- mentat:managed:start fleet-place -->\nx\n<!-- mentat:managed:end fleet-place -->\n"
        si.write(self.root)
        (self.root / "AGENTS.md").write_text(fleet + "\n" + self.agents(), encoding="utf-8")
        r = self.tool("mentat_self_image.py", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ORDER", r.stdout)
        si.write(self.root)
        text = self.agents()
        self.assertTrue(text.startswith(si.START))
        self.assertLess(text.index(si.END), text.index("fleet-place"))
        self.assertEqual(text.count(si.START), 1)

    def test_a_placeholder_left_in_the_block_is_red_until_the_name_is_set(self):
        self.brain("hu", {"default": "asszisztens", "installed": ["asszisztens"]})
        m = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
        del m["agent"]["name"]
        (self.root / "mentat.json").write_text(json.dumps(m), encoding="utf-8")
        si.write(self.root)
        r = self.tool("mentat_self_image.py", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("OPEN placeholder <ügynök neve TBD>", r.stdout)
        r = self.tool("mentat_scaffold_check.py", "--lang", "hu")
        self.assertIn("OPEN placeholder <ügynök neve TBD> in self-image", r.stdout)
        m["agent"]["name"] = "Thufir"
        (self.root / "mentat.json").write_text(json.dumps(m), encoding="utf-8")
        si.write(self.root)
        self.assertEqual(self.tool("mentat_self_image.py", "--check").returncode, 0)

    def test_a_missing_block_is_red(self):
        (self.root / "AGENTS.md").write_text("# x\n", encoding="utf-8")
        r = self.tool("mentat_self_image.py", "--check", "--lang", "hu")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISSING", r.stdout)


if __name__ == "__main__":
    unittest.main()
