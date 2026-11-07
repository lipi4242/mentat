"""BEKOTES step 8: the sync-to.sh path must exist in a RELEASED engine tree (sync-to.sh at root)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import re
import shutil
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent


def sync_command(lang):
    text = (HERE / ("BEKOTES.%s.md" % lang)).read_text(encoding="utf-8")
    section = re.search(r"^## 6–8\..*?(?=^## )", text, re.M | re.S).group(0)
    block = re.search(r"```bash\n(.*?)```", section, re.S).group(1)
    line = next(ln for ln in block.splitlines() if "sync-to.sh" in ln)
    return section, line.split("#", 1)[0].split()


class EngineStep(unittest.TestCase):
    def test_sync_path_exists_in_released_layout_and_only_pack(self):
        home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        released = home / "src" / "mentat" / "engine"
        released.mkdir(parents=True)
        (released / "sync-to.sh").write_text("#!/bin/sh\n")  # released layout: no release/ dir
        for lang in ("hu", "en"):
            section, words = sync_command(lang)
            script = next(w for w in words if w.endswith("sync-to.sh"))
            path = pathlib.Path(script.replace("~", str(home), 1) if script.startswith("~/") else script)
            self.assertTrue(path.is_file(), (lang, script))
            self.assertEqual(words[words.index(script) + 1:], [".", "--pack", "bekotes", "--only-pack"], lang)
            self.assertIn("release/sync-to.sh", section, lang)  # the dev-checkout variant is named too

    def test_steps_2_to_4_are_one_call(self):
        for lang in ("hu", "en"):
            text = (HERE / ("BEKOTES.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertIn("$BK elokeszit --business", text, lang)
            self.assertIn("$BK leltar --osszefoglalo --business", text, lang)
            self.assertIn('"from":', text, lang)
            self.assertNotIn("$BK memoria stage", text, lang)


if __name__ == "__main__":
    unittest.main()
