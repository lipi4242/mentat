"""F-41 in the role guard: the identity gate through the real hook (ask interactively, deny
headless), the SessionStart cache, and the gate's own files that the agent never writes."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import stat
import unittest

from test_guard_kint import KintBase

ADDR = "teszt.elek@example.com"
OPENALEX = "https://api.openalex.org/works?filter=x&mailto=" + ADDR


class IdentityGate(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.home / ".mentat").mkdir()
        (self.home / ".mentat" / "identitas.txt").write_text(ADDR + "\n")

    def reason(self, tool, inp, mode):
        r = self.run_guard(self.payload(tool, inp, mode))
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_polite_pool_address_asks_and_headless_denies_without_a_detour(self):
        self.assertEqual(self.d("WebFetch", {"url": OPENALEX, "prompt": "x"}), "ask")
        self.assertEqual(self.d("WebFetch", {"url": OPENALEX, "prompt": "x"}, mode="bypassPermissions"), "deny")
        why = self.reason("WebFetch", {"url": OPENALEX, "prompt": "x"}, "bypassPermissions")
        self.assertIn("mailto", why)
        self.assertIn("kerülőutat", why)
        ua = 'curl -s -A "kutato (mailto:%s)" https://api.crossref.org/works' % ADDR
        self.assertEqual(self.bash(ua), "ask")

    def test_without_the_address_or_to_a_first_party_it_stays_open(self):
        self.assertEqual(self.d("WebFetch", {"url": "https://api.openalex.org/works?filter=x", "prompt": "x"}), "allow")
        self.assertEqual(self.d("WebSearch", {"query": "openalex polite pool"}), "allow")
        self.assertEqual(self.bash("curl -s https://admin.example.com/me -H 'X-U: %s'" % ADDR), "allow")
        self.assertEqual(self.d("Write", {"file_path": str(self.root / "agy" / "x.md"), "content": ADDR}), "allow")

    def test_the_gates_own_files_are_never_the_agents(self):
        for tool, inp in (("Write", {"file_path": str(self.home / ".mentat" / "elsofel.txt"), "content": "*"}),
                          ("Edit", {"file_path": str(self.home / ".mentat" / "identitas.txt"),
                                    "old_string": ADDR, "new_string": ""}),
                          ("Write", {"file_path": str(self.root / ".mentat" / "identitas.json"), "content": "{}"}),
                          ("Bash", {"command": "echo '*' >> ~/.mentat/elsofel.txt"}),
                          ("Bash", {"command": "rm -f .mentat/identitas.json"}),
                          ("Write", {"file_path": str(self.home / ".mentat" / "kepessegfa-megosztas.txt"),
                                     "content": "own.project.x"}),  # the USER's export list (phase 3)
                          ("Bash", {"command": "echo own.project.x >> ~/.mentat/kepessegfa-megosztas.txt"})):
            self.assertEqual(self.d(tool, inp), "deny", (tool, inp))

    def test_session_start_caches_the_identifiers_privately(self):
        import subprocess
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], capture_output=True)
        (self.root / ".gitignore").write_text(".mentat/\n")  # the cache only where git ignores it
        r = self.run_guard({"hook_event_name": "SessionStart", "session_id": "s1"}, args=("--session-start",))
        self.assertEqual(r.returncode, 0, r.stderr)
        cache = self.root / ".mentat" / "identitas.json"
        self.assertIn(ADDR, json.loads(cache.read_text())["ids"])
        self.assertEqual(stat.S_IMODE(os.stat(cache).st_mode), 0o600)
        (self.home / ".mentat" / "identitas.txt").unlink()
        self.assertEqual(self.d("WebFetch", {"url": OPENALEX, "prompt": "x"}), "ask")  # from the cache


class BrainRule(unittest.TestCase):
    def test_the_brain_says_it_in_one_sentence(self):  # Krisz, 2026-10-24
        here = os.path.dirname(os.path.abspath(__file__))
        for lang, word in (("hu", "üresen marad"), ("en", "leave the field empty")):
            text = open(os.path.join(here, "..", "manifest", "scaffold-agents.%s.md" % lang), encoding="utf-8").read()
            self.assertIn("mailto", text, lang)
            self.assertIn(word, text, lang)


if __name__ == "__main__":
    unittest.main()
