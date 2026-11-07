"""Codex adversarial review (2026-10-23) on the boundary guard.

2. any tool that names a path (MCP, LSP, WebFetch file://) is judged like Read;
3. an ALLOW never matches by lowercase, and a consent is the file's identity (dev+inode);
4. the guard cannot be swapped: parent folders, its imports, interpreters on PATH.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import shutil
import subprocess
import unittest
from unittest import mock

from _bekotes_repo import env, leltar, make_agent, szerepek
from test_guard_kint import KintBase


class AnyTool(KintBase):
    def test_paths_in_other_tools_are_judged(self):
        h = self.home
        for tool, inp in (("mcp__fs__read_file", {"path": "~/business/x.txt"}),
                          ("WebFetch", {"url": "file://%s" % (h / "business/x.txt"), "prompt": "x"}),
                          ("LSP", {"operation": "hover", "filePath": str(self.mem)}),
                          ("mcp__x__y", {"args": {"files": [str(self.mem)]}})):
            self.assertEqual(self.d(tool, inp), "ask", (tool, inp))
        for tool, inp in (("mcp__fs__read_file", {"path": str(self.root / "agy/a.md")}),
                          ("Agent", {"prompt": "nézd meg az agy/a.md-t"}), ("TodoWrite", {"todos": []})):
            self.assertEqual(self.d(tool, inp), "allow", (tool, inp))


class Identity(KintBase):
    def test_allow_does_not_match_by_lowercase(self):
        upper = str(self.root).replace("/agent", "/AGENT")
        self.assertEqual(self.d("Read", {"file_path": upper + "/agy/a.md"}), "ask")

    def test_consent_is_the_file_not_its_name(self):
        x = self.home / "business" / "x.txt"
        self.post("Read", {"file_path": str(x)})
        os.link(x, self.home / "business" / "hard.txt")  # the same file under another name
        self.assertEqual(self.d("Read", {"file_path": str(self.home / "business/hard.txt")}), "allow")
        x.rename(self.home / "business" / "old.txt")
        x.write_text("new\n")  # replaced at the approved path
        self.assertEqual(self.d("Read", {"file_path": str(x)}), "ask")


class CaseSensitiveDisk(KintBase):
    def test_approving_one_spelling_does_not_open_the_other(self):  # CISO + Codex 3
        d = self.home / "business"
        (d / "Foo.txt").write_text("1\n")
        if (d / "foo.txt").exists():
            self.skipTest("case-insensitive disk here: Foo.txt and foo.txt are one file (inode rule covers it)")
        (d / "foo.txt").write_text("2\n")
        self.post("Read", {"file_path": str(d / "Foo.txt")})
        self.assertEqual(self.d("Read", {"file_path": str(d / "Foo.txt")}), "allow")
        self.assertEqual(self.d("Read", {"file_path": str(d / "foo.txt")}), "ask")


class HookFailureBlocks(unittest.TestCase):
    """Claude Code fails a command hook OPEN unless onFailure is "block" (docs, >= 2.1.295)."""

    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.assertEqual(leltar(self.root).returncode, 0)
        self.assertEqual(szerepek(self.root).returncode, 0)
        s = json.loads((self.root / ".claude/settings.json").read_text())
        self.pre = s["hooks"]["PreToolUse"][-1]["hooks"][0]

    def run_hook(self, **env_over):
        payload = {"session_id": "s1", "cwd": str(self.root), "tool_name": "Read",
                   "tool_input": {"file_path": "README.md"}}
        e = dict(env(self.root), CLAUDE_PROJECT_DIR=str(self.root), **env_over)
        return subprocess.run(["/bin/sh", "-c", self.pre["command"]], input=json.dumps(payload),
                              capture_output=True, text=True, env=e, cwd=self.root)

    def test_the_handler_blocks_on_failure_with_a_short_timeout(self):
        self.assertEqual(self.pre.get("onFailure"), "block")
        self.assertLessEqual(self.pre.get("timeout", 600), 10)

    def test_crash_import_error_and_missing_python_are_failures_not_allows(self):
        (self.root / ".mentat/bin/bekotes/szerep_dontes.py").write_text("raise ImportError('broken')\n")
        r = self.run_hook()
        self.assertNotEqual(r.returncode, 0)  # a failure: onFailure blocks it
        self.assertNotIn('"allow"', r.stdout)
        r = self.run_hook(PATH="/nonexistent")  # no python3 at all
        self.assertNotEqual(r.returncode, 0)


class FailureModes(HookFailureBlocks):
    """CISO F-39: no failure mode may look like a clean allow (exit 0 and empty or valid allow)."""

    def silent_allow(self, r):
        if r.returncode != 0:
            return False  # a failure: onFailure "block" blocks it
        if not r.stdout.strip():
            return True
        try:
            out = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
        except (ValueError, KeyError, TypeError):
            return False  # malformed output: blocked as a failure
        return out == "allow"

    def test_exit1_bad_json_missing_script_and_timeout(self):
        guard = self.root / ".mentat/bin/bekotes/szerep_guard.py"
        for body in ("raise SystemExit(1)\n", "print('{nem json')\n"):
            guard.write_text(body)
            self.assertFalse(self.silent_allow(self.run_hook()), body)
        guard.unlink()
        self.assertFalse(self.silent_allow(self.run_hook()))
        self.assertEqual(self.pre["onFailure"], "block")  # a timeout is a failure too
        self.assertLessEqual(self.pre["timeout"], 10)


class SelfProtection(KintBase):
    roles = False

    def test_parents_and_interpreters_cannot_be_swapped(self):
        (self.root / ".mentat").mkdir(exist_ok=True)
        (self.root / ".mentat" / "engedelyek.json").write_text('{"engedelyek": []}')
        before = (self.root / ".mentat" / "engedelyek.json").read_text()
        for cmd in ("mv .mentat .mentat.old", "rm -rf .mentat", "mv .mentat/naplo /tmp/n"):
            self.assertEqual(self.bash(cmd), "deny", cmd)
        for cmd in ("mv .claude .claude.old", "ln -sfn /tmp/evil .mentat/bin/bekotes", "rm -rf .mentat/bin",
                    "cp /tmp/x .mentat/bin/bekotes/json.py"):
            self.assertEqual(self.bash(cmd), "ask", cmd)
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}):
            self.assertEqual(self.bash("cp agy/a.md bin/python3"), "ask")
            self.assertEqual(self.bash("cp README.md bin/notes"), "allow")
        self.assertEqual((self.root / ".mentat" / "engedelyek.json").read_text(), before)


class ImportShadow(unittest.TestCase):
    def test_a_module_next_to_the_tools_cannot_replace_the_guards(self):
        root = make_agent()
        self.addCleanup(shutil.rmtree, root, True)
        self.assertEqual(leltar(root).returncode, 0)
        self.assertEqual(szerepek(root).returncode, 0)
        (root / ".mentat/bin/shlex.py").write_text(  # would blind the Bash parser if it were imported
            "class shlex:\n    def __init__(self, *a, **k):\n        self.whitespace_split = True\n"
            "    def __iter__(self):\n        return iter([])\n")
        s = json.loads((root / ".claude/settings.json").read_text())
        cmd = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]][0]
        payload = {"session_id": "s1", "cwd": str(root), "permission_mode": "default", "tool_name": "Bash",
                   "tool_input": {"command": "cat ~/.ssh/id_rsa"}}
        r = subprocess.run(["sh", "-c", cmd], input=json.dumps(payload), capture_output=True, text=True,
                           env=dict(env(root), CLAUDE_PROJECT_DIR=str(root)), cwd=root)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask", r.stderr)


if __name__ == "__main__":
    unittest.main()
