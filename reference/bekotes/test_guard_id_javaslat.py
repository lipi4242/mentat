"""F-41: the suggested first-party list, the USER's yes before it is written, and the cache only
where git ignores it (CISO #81)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from test_guard_kint import KintBase

HERE = Path(__file__).resolve().parent
TOOL = HERE / "szerep_id_javaslat.py"
ADDR = "teszt.elek@example.com"


class Suggest(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        git = lambda *a: subprocess.run(["git", "-C", str(self.root), *a], capture_output=True)  # noqa: E731
        git("init", "-q")
        git("remote", "add", "origin", "https://github.com/acme/agent.git")
        (self.root / "agy" / "connectors").mkdir(parents=True, exist_ok=True)
        (self.root / "agy" / "connectors" / "crm.md").write_text("# CRM\nAPI: https://api.sajatcrm.example.org/v1\n")
        (self.root / "projects" / "app").mkdir(parents=True)
        (self.root / "projects" / "app" / "wrangler.toml").write_text('routes = [{ pattern = "app.example.net/*" }]\n')
        (self.root / "projects" / "app" / "README.md").write_text("Élesben: https://lista.acme.workers.dev\n")
        (self.root / "projects" / "app" / "front").mkdir()
        (self.root / "projects" / "app" / "front" / "wrangler.jsonc").write_text(
            '{"routes": [{"pattern": "front.example.org", "custom_domain": true}]}\n')
        (self.root / "AGENTS.md").write_text("Admin: https://admin-api.acme.workers.dev/health\n")
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh" / "config").write_text("Host doboz\n  HostName box.example.net\nHost *\n  User x\n")
        (self.home / ".ssh" / "known_hosts").write_text(
            "198.51.100.7 ssh-ed25519 AAAA\n[nas.example.net]:2222,203.0.113.9 ssh-rsa AAAA\n|1|hash= ssh-rsa AAAA\n"
            "github.com ssh-ed25519 AAAA\n")
        (self.root / "projects" / "app" / "node_modules").mkdir()
        (self.root / "projects" / "app" / "node_modules" / "wrangler.toml").write_text('pattern = "vendor.example.org"\n')

    def tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True, env=dict(os.environ))

    def test_the_four_sources_and_nothing_already_first_party(self):
        out = self.tool().stdout
        for line in ("github:acme", "api.sajatcrm.example.org", "app.example.net", "lista.acme.workers.dev",
                     "front.example.org", "admin-api.acme.workers.dev", "doboz", "box.example.net",
                     "198.51.100.7", "nas.example.net", "203.0.113.9"):
            self.assertIn(line, out)
        for gone in ("github.com ", "vendor.example.org", "*"):
            self.assertNotIn(gone + "    #", out)
        self.assertFalse((self.home / ".mentat" / "elsofel.txt").exists())  # listing writes nothing

    def test_write_takes_only_named_suggested_lines(self):
        r = self.tool("--write", "github:acme", "evil.example.org")
        self.assertEqual(r.returncode, 1)
        f = self.home / ".mentat" / "elsofel.txt"
        self.assertEqual(f.read_text().split(), ["github:acme"])
        self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)

    def test_the_guard_asks_the_user_for_write_and_denies_headless(self):
        cmd = "python3 .mentat/bin/bekotes/szerep_id_javaslat.py --write github:acme"
        self.assertEqual(self.bash(cmd), "ask")
        self.assertEqual(self.bash(cmd, mode="bypassPermissions"), "deny")
        self.assertEqual(self.bash("python3 .mentat/bin/bekotes/szerep_id_javaslat.py"), "allow")

    def session(self):
        r = self.run_guard({"hook_event_name": "SessionStart", "session_id": "s1"}, args=("--session-start",))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""

    def test_session_start_suggests_once_while_the_list_is_empty(self):
        note = self.session()
        self.assertIn("szerep_id_javaslat", note)
        for host in ("box.example.net", "doboz", "github:acme", "app.example.net"):  # a count, never the hosts
            self.assertNotIn(host, note)
        self.tool("--write", "github:acme")
        self.assertNotIn("szerep_id_javaslat", self.session())

    def test_no_cache_where_git_does_not_ignore_it(self):  # CISO #81, 1
        (self.home / ".mentat").mkdir(exist_ok=True)
        (self.home / ".mentat" / "identitas.txt").write_text(ADDR + "\n")
        (self.root / ".gitignore").write_text("")
        self.session()
        self.assertFalse((self.root / ".mentat" / "identitas.json").exists())
        (self.root / ".gitignore").write_text(".mentat/\n")
        self.session()
        self.assertIn(ADDR, json.loads((self.root / ".mentat" / "identitas.json").read_text())["ids"])


if __name__ == "__main__":
    unittest.main()
