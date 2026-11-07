"""Friction #8: the read guard must exist BEFORE any onboarding.

Step 1 of the initialization vendors the guard (every module it imports) into
.mentat/bin/bekotes/, and mentat_scaffold.py hooks it into .claude/settings.json.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
BEKOTES = HERE.parent / "bekotes"


def guard_modules():
    """The bekotes/ modules szerep_guard.py imports, transitively."""
    todo, seen = ["szerep_guard"], set()
    while todo:
        name = todo.pop()
        if name in seen or not (BEKOTES / (name + ".py")).is_file():
            continue
        seen.add(name)
        text = (BEKOTES / (name + ".py")).read_text(encoding="utf-8")
        todo += re.findall(r"^\s*(?:from|import) (\w+)", text, re.M)
    return {n + ".py" for n in seen}


class GuardAtInit(unittest.TestCase):
    def test_step1_vendors_every_guard_module(self):
        for lang in ("hu", "en"):
            name = "initialization.%s.md" % lang if lang == "hu" else "initialization.md"
            text = (HERE.parent / name).read_text(encoding="utf-8")
            m = re.search(r'-o "\.mentat/bin/bekotes/#1" "[^"]*/reference/bekotes/\{([^}]*)\}"', text)
            self.assertIsNotNone(m, lang)
            self.assertTrue(guard_modules() <= set(m.group(1).split(",")),
                            (lang, guard_modules() - set(m.group(1).split(","))))

    def test_scaffold_hooks_the_guard(self):
        root, home = pathlib.Path(tempfile.mkdtemp()), tempfile.mkdtemp()
        env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))
        for _ in range(2):
            r = subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                                "--repo", str(root), "--base", "https://example.com/kit/v9.9.9/"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for event in ("PreToolUse", "PostToolUse", "SessionStart"):
            cmds = [h["command"] for e in s["hooks"][event] for h in e["hooks"]]
            self.assertEqual(sum("szerep_guard.py" in c for c in cmds), 1, (event, cmds))
        # the native layer next to the hook: deny rules win over every allow
        for rule in ("Read(~/.ssh/**)", "Read(~/.config/**)", "Read(//**/.env*)",
                     "Read(~/.claude/projects/*/memory/**)", "Read(~/.claude/projects/**/*.jsonl)"):
            self.assertEqual(s["permissions"]["deny"].count(rule), 1, rule)


if __name__ == "__main__":
    unittest.main()
