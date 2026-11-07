"""Friction #8 (F-38): the working-folder boundary, with or without roles.

Outside the folder (HOME, other homes, ~/.claude*, other repos) every Read/Grep/Glob/Bash
read needs the USER: interactive -> "ask", headless -> "deny" with a channel message. An
approved call (PostToolUse) puts its paths on the consent list, which the agent cannot
write; every outside decision is logged without content.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_guard import GUARD, GuardBase, make_repo

SECRET = "titok-ertek-42"


class KintBase(GuardBase):
    roles = True

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)
        p = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        p.start()
        self.addCleanup(p.stop)
        for var in ("MENTAT_HEADLESS", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_ENTRYPOINT"):
            os.environ.pop(var, None)  # the runner's own session must not leak in
        src = make_repo() if self.roles else make_repo(roles={})
        self.root = self.home / "agent"
        shutil.move(str(src), str(self.root))
        mem = self.home / ".claude" / "projects" / "-Users-x-other" / "memory"
        mem.mkdir(parents=True)
        (mem / "ugyfel.md").write_text(SECRET + "\n")
        (self.home / ".claude-personal" / "projects").mkdir(parents=True)
        (self.home / "code" / "other").mkdir(parents=True)
        (self.home / "code" / "other" / ".env").write_text("LINEAR_API_KEY=%s\n" % SECRET)
        (self.home / "business").mkdir()
        (self.home / "business" / "x.txt").write_text("1\n")
        (self.root / "agy" / "a.md").write_text("a\n")
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(self.root.resolve()))
        own = self.home / ".claude" / "projects" / slug / "tool-results"
        own.mkdir(parents=True)
        (own / "out.txt").write_text("ok\n")
        self.own = own / "out.txt"
        self.mem = mem / "ugyfel.md"

    def payload(self, tool, inp, mode="default", sid="s1"):
        return {"tool_name": tool, "tool_input": inp, "cwd": str(self.root), "permission_mode": mode,
                "session_id": sid}

    def d(self, tool, inp, role=None, mode="default", sid="s1"):
        r = self.run_guard(self.payload(tool, inp, mode, sid), role)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else "allow"

    def bash(self, cmd, role=None, mode="default", sid="s1"):
        return self.d("Bash", {"command": cmd}, role, mode, sid)

    def post(self, tool, inp, mode="default", sid="s1"):
        r = self.run_guard(self.payload(tool, inp, mode, sid), None, ["--post"])
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)


OUTSIDE_TOOLS = lambda h: (  # noqa: E731
    ("Read", {"file_path": str(h / ".claude/projects/-Users-x-other/memory/ugyfel.md")}),
    ("Read", {"file_path": str(h / ".CLAUDE/projects/-Users-x-other/memory/ugyfel.md")}),
    ("Read", {"file_path": str(h / "code/other/README.md")}),
    ("Grep", {"pattern": "KEY", "path": str(h / ".claude-personal/projects")}),
    ("Grep", {"pattern": "titok", "path": str(h)}),
    ("Glob", {"pattern": str(h / "business") + "/**"}),
    ("Glob", {"pattern": "**/*.md", "path": "/"}))
OUTSIDE_BASH = ("cat ~/.claude/projects/-Users-x-other/memory/ugyfel.md", "head -5 $HOME/business/x.txt",
                "find ~ -name '*.md'", "grep -r KEY ~/code", "rg titok ~/business", "git -C ~/code/other log",
                "ls ~", "ls ..", "cd ~/business && cat x.txt", "cd && ls", "find / -name ugyfel.md",
                "cat link/projects/-Users-x-other/memory/ugyfel.md", "cat ~/BUSINESS/x.txt",
                "D=~/.claude; cat $D/projects/-Users-x-other/memory/ugyfel.md",
                "python3 -c \"print(open('%s').read())\"")


class Boundary(KintBase):
    def setUp(self):
        super().setUp()
        (self.root / "link").symlink_to(self.home / ".claude")

    def test_outside_asks_interactively_for_every_role(self):
        for tool, inp in OUTSIDE_TOOLS(self.home):
            for role in (None, "fejleszto"):
                self.assertEqual(self.d(tool, inp, role), "ask", (role, tool, inp))
        for cmd in OUTSIDE_BASH:
            cmd = cmd.replace("%s", str(self.mem))
            for role in (None, "fejleszto"):
                self.assertEqual(self.bash(cmd, role), "ask", "%s: %s" % (role, cmd))

    def test_headless_denies_and_says_ask_on_the_channel(self):
        (self.root / ".claude").mkdir(exist_ok=True)
        cases = [("bypassPermissions", None), ("dontAsk", None), ("auto", None), ("default", "env")]
        for mode, env in cases:
            with mock.patch.dict(os.environ, {"MENTAT_HEADLESS": "1"} if env else {}):
                self.assertEqual(self.bash("cat ~/business/x.txt", mode=mode), "deny", mode)
        (self.root / ".claude" / "fleet.json").write_text(json.dumps({"agent": "rocky"}))
        r = self.run_guard(self.payload("Read", {"file_path": str(self.mem)}))
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("Telegram", out["permissionDecisionReason"])
        self.assertIn("AskUserQuestion", out["permissionDecisionReason"])

    def test_inside_and_own_tooling_allowed(self):
        for tool, inp in (("Read", {"file_path": str(self.root / "agy/a.md")}), ("Read", {"file_path": str(self.own)}),
                          ("Grep", {"pattern": "a", "path": "agy"}), ("Glob", {"pattern": "agy/**"})):
            self.assertEqual(self.d(tool, inp), "allow", (tool, inp))
        for cmd in ("ls", "cat agy/a.md", "git status", "python3 --version", "ls /usr/bin",
                    "~/src/mentat/engine/sync-to.sh . --pack cases", "cat %s" % self.own,
                    "REF=~/src/mentat/reference; ls $REF", "ls ~/src/mentat/fleet/bin"):
            self.assertEqual(self.bash(cmd), "allow", cmd)


class Consent(KintBase):
    def test_approved_call_becomes_consent_and_is_logged_without_content(self):
        self.assertEqual(self.bash("cat ~/business/x.txt"), "ask")
        self.post("Bash", {"command": "cat ~/business/x.txt"})
        self.assertEqual(self.bash("cat ~/business/x.txt"), "allow")
        self.assertEqual(self.bash("ls ~/code"), "ask")
        log = (self.root / ".mentat/naplo/kivuli.jsonl").read_text()
        rows = [json.loads(x) for x in log.splitlines()]
        self.assertEqual([r["dontes"] for r in rows], ["ask", "jovahagyva", "allow", "ask"])
        self.assertNotIn("cat ", log)
        listed = json.loads((self.root / ".mentat/engedelyek.json").read_text())["engedelyek"]
        self.assertEqual([e["ut"] for e in listed], [str(self.home / "business/x.txt")])

    def test_consent_is_exact_per_file_and_operation_and_never_a_root(self):  # CISO B-1
        self.post("Grep", {"pattern": "x", "path": str(self.home)}, sid="s1")
        self.post("Bash", {"command": "ls /tmp"}, sid="s1")
        self.assertEqual(self.d("Read", {"file_path": str(self.mem)}), "ask")
        self.assertEqual(self.d("Write", {"file_path": str(self.home / ".zshrc"), "content": "x"}), "ask")
        self.post("Read", {"file_path": str(self.home / "business/x.txt")})
        self.assertEqual(self.d("Read", {"file_path": str(self.home / "business/x.txt")}), "allow")
        self.assertEqual(self.d("Edit", {"file_path": str(self.home / "business/x.txt")}), "ask")  # read != write
        self.assertEqual(self.d("Read", {"file_path": str(self.home / "business/y.txt")}), "ask")  # exact
        self.post("Bash", {"command": "cat ~/business/nincs"})  # not a folder: kept as an exact path
        self.assertEqual(self.bash("cat ~/business/nincs/titok.txt"), "ask")  # not as a prefix

    def test_folder_sweep_is_for_this_session_only(self):
        self.post("Grep", {"pattern": "x", "path": str(self.home / "business")}, sid="s7")
        self.assertEqual(self.bash("cat ~/business/x.txt", sid="s7"), "allow")
        self.assertEqual(self.bash("cat ~/business/x.txt", sid="s8"), "ask")

    def test_shared_temp_and_other_config_roots_are_outside(self):  # CISO B-2, B-3
        other = self.home / ".claude-personal" / "plugins"
        other.mkdir(parents=True)
        (self.home / ".config" / "rocky").mkdir(parents=True)
        for cmd in ("cat /private/tmp/claude-other/x.txt", "ls /tmp", "ls /Volumes", "ls %s" % other):
            self.assertEqual(self.bash(cmd), "ask", cmd)
        self.assertEqual(self.bash("ls ~/.claude/plugins"), "allow")  # the active root (HOME/.claude)

    def test_headless_post_records_nothing(self):
        self.post("Bash", {"command": "cat ~/business/x.txt"}, mode="bypassPermissions")
        self.assertFalse((self.root / ".mentat/engedelyek.json").exists())

    def test_agent_cannot_write_consent_or_log(self):
        for tool, inp in (("Write", {"file_path": str(self.root / ".mentat/engedelyek.json"), "content": "{}"}),
                          ("Edit", {"file_path": ".mentat/ENGEDELYEK.json"}),
                          ("Bash", {"command": "echo '{\"engedelyek\": [{\"ut\": \"/\"}]}' > .mentat/engedelyek.json"}),
                          ("Bash", {"command": "python3 -c \"open('.mentat/engedelyek.json','w')\""}),
                          ("Bash", {"command": "truncate -s0 .mentat/naplo/kivuli.jsonl"})):
            for role in (None, "fejleszto"):
                self.assertEqual(self.d(tool, inp, role), "deny", (role, tool, inp))
        self.assertEqual(self.bash("python3 .mentat/bin/bekotes/szerep_engedely.py lista"), "allow")


class NoRoles(KintBase):
    roles = False

    def test_boundary_without_roles(self):
        self.assertEqual(self.bash("grep -r KEY ~/code"), "ask")
        self.assertEqual(self.bash("git push origin main"), "allow")  # no role rules without roles


class FleetAgent(KintBase):
    def test_own_bridge_allowed_other_agents_asked(self):
        (self.root / ".claude").mkdir(exist_ok=True)
        (self.root / ".claude" / "fleet.json").write_text(json.dumps({"agent": "rocky"}))
        for name in ("rocky", "paul"):
            (self.home / ".config" / name / "sub-etha").mkdir(parents=True)
        for cmd in ("node ~/.config/rocky/sub-etha/send.mjs --chat 1 --text-stdin",
                    "set -a; . ~/.config/rocky/telegram.env; set +a"):
            self.assertEqual(self.bash(cmd), "allow", cmd)
        self.assertEqual(self.bash("cat ~/.config/paul/telegram.env"), "deny")  # headless: fleet
        self.assertEqual(self.bash("cat ~/.config/rocky/claude-auth.env"), "deny")  # own folder, but a secret (B-4)


if __name__ == "__main__":
    unittest.main()
