"""A fresh install carries the role tools: the documented custom-role steps (roles.md, Custom
roles) run right after it, with nothing fetched later, and mentat_verify names them when missing.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TREE = HERE.parent.parent  # release/
sys.path.insert(0, str(HERE))
import mentat_verify as mv  # noqa: E402

DOCS = {"en": ("initialization.md", "brain"), "hu": ("initialization.hu.md", "agy")}
HEAD = {"en": "## Role self-image", "hu": "## Szerep önkép"}
MINE = "The business's finance lead: every number has a source."


def install(doc):
    """What the curl step of the given initialization doc does, from the local tree."""
    root = pathlib.Path(tempfile.mkdtemp())
    for dest, src in mv.listing((TREE / "reference" / doc).read_text(encoding="utf-8")):
        (root / ".mentat/bin" / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TREE / src, root / ".mentat/bin" / dest)
    return root


class CustomRoleAfterInstall(unittest.TestCase):
    def run_tool(self, root, *args):
        env = dict(os.environ, HOME=tempfile.mkdtemp())
        env.pop("MENTAT_ROLE", None)
        return subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")

    def test_the_documented_custom_role_steps_run_without_a_download(self):
        for lang, (doc, brain) in DOCS.items():
            with self.subTest(lang=lang):
                root = install(doc)
                self.addCleanup(shutil.rmtree, root, True)
                r = self.run_tool(root, ".mentat/bin/mentat_cli.py", "init-brain", "--name", "Bob",
                                  "--language", lang, "--brain-root", brain, "--version", "0.6.1")
                self.assertEqual(r.returncode, 0, r.stderr)
                role = root / brain / "szerepek" / "penzugy.md"
                role.parent.mkdir(parents=True)
                role.write_text("---\nname: penzugy\ndeny: []\n---\n\n# penzugy\n\n%s\n\n%s\n"
                                % (HEAD[lang], MINE), encoding="utf-8")
                # step 3: a shipped role (template only) next to the custom one, then its block
                r = self.run_tool(root, ".mentat/bin/mentat_cli.py", "roles",
                                  "--default", "asszisztens", "--install", "penzugy")
                self.assertEqual(r.returncode, 0, r.stderr)
                r = self.run_tool(root, ".mentat/bin/bekotes/bekotes.py", "onkep", "--alkalmaz")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                block = (root / brain / "szerep-onkep.md").read_text(encoding="utf-8")
                self.assertIn("szerep=penzugy alap=custom", block)
                self.assertIn(MINE, block)
                self.assertIn("szerep=asszisztens alap=sha256:", block)


class VerifyNamesMissingRoleTools(unittest.TestCase):
    def test_a_missing_role_tool_is_named(self):
        root = install("initialization.md")
        self.addCleanup(shutil.rmtree, root, True)
        bin_dir = root / ".mentat/bin"
        shutil.copyfile(TREE / "release.json", bin_dir / "release.json")
        self.assertIsNone(mv.verify(bin_dir))
        for rel in ("bekotes/bekotes.py", "bekotes/szerep_onkep.py", "bekotes/szerepek/asszisztens.en.md"):
            with self.subTest(rel=rel):
                gone = bin_dir / rel
                kept = gone.read_bytes()
                gone.unlink()
                msg = mv.verify(bin_dir) or ""
                gone.write_bytes(kept)
                self.assertIn(rel, msg)


if __name__ == "__main__":
    unittest.main()
