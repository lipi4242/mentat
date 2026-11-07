"""Odd files never turn the guard into an error that denies every tool (fail-closed by accident).

Every external file the F-41 and capability gates read (the USER's two files, the Claude account
files, the identity cache, local.json, the receipts and their ledger, the consent list, the user
settings and the installed-plugins list) is filled
with odd shapes: empty, null, a string, a list, a number, truncated JSON, binary, wrong field
types. The guard must answer as it would without that file, in the safe direction: the identity
gate still asks, a new capability is still denied with the finder's command, and no answer is the
"guard error" deny. The role guard's own fail-closed on a broken mentat.json is a separate,
deliberate rule (no role, nothing is allowed) and is not fuzzed here.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import sys
import unittest

from test_guard_kint import KintBase

ADDR = "teszt.elek@example.com"
OPENALEX = "https://api.openalex.org/works?mailto=" + ADDR
R = ".mentat/state/capability-receipts"
SHAPES = [b"", b"null", b'"x"', b"[1, 2]", b"7", b"{", b"\xff\xfe\x00\x81bin", b'{"a": 1}', b"\xc3\x28 latin"]
FIELDS = {
    "home:.claude.json": [b'{"oauthAccount": "x"}', b'{"oauthAccount": {"emailAddress": 5}}', b'{"oauthAccount": [1]}'],
    "root:.mentat/identitas.json": [b'{"ids": "x", "gh_logins": "y"}', b'{"ids": [1, null, {}], "gh_logins": [2]}'],
    "root:.mentat/local.json": [b'{"admin": "x", "fleet": [1]}', b'{"admin": {"url": 5}, "fleet": {"host": []}}'],
    "root:%s/_ledger.jsonl" % R: [b'[1]\n7\n{"receipt": 5, "sha256": [], "decided_at": null}\n'],
    "root:%s/r.json" % R: [b'{"decision": "x"}', b'{"decision": {"decided_at": 5}}'],
    "root:.mentat/engedelyek.json": [b'{"engedelyek": "x"}', b'{"engedelyek": [1, {"ut": 5}]}'],
    "home:.claude/settings.json": [b'{"hooks": "x", "enabledPlugins": [1]}', b'{"hooks": {"PreToolUse": [null, "x"]}}'],
    "home:.claude/plugins/installed_plugins.json": [b'{"plugins": [1]}', b'{"plugins": {"a@b": "x"}}'],
}
TARGETS = ["home:.mentat/identitas.txt", "home:.mentat/elsofel.txt", "home:.claude/.claude.json"] + list(FIELDS)


class OddFiles(KintBase):
    roles = False

    def place(self, target, content):
        where, rel = target.split(":", 1)
        p = (self.home if where == "home" else self.root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def answer(self, tool, inp):
        r = self.run_guard(self.payload(tool, inp))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else {}
        return out.get("permissionDecision", "allow"), out.get("permissionDecisionReason", "")

    def test_every_reader_survives_every_odd_shape(self):
        for target in TARGETS:
            for content in SHAPES + FIELDS.get(target, []):
                with self.subTest(target=target, content=content[:30]):
                    self.setUp()
                    if target != "home:.mentat/identitas.txt":  # a valid source of the address
                        self.place("home:.mentat/identitas.txt", (ADDR + "\n").encode())
                    else:
                        self.place("home:.claude.json", json.dumps({"oauthAccount": {"emailAddress": ADDR}}).encode())
                    self.place(target, content)
                    decision, why = self.answer("WebFetch", {"url": OPENALEX, "prompt": "x"})
                    self.assertNotIn("hibája", why)
                    self.assertEqual(decision, "ask", why)  # the identity gate still asks
                    decision, why = self.answer("Write", {"file_path": str(self.root / "projects" / "x" / "uj.py"),
                                                          "content": "x"})
                    self.assertNotIn("hibája", why)
                    self.assertEqual(decision, "deny")
                    self.assertIn("where --find", why)  # denied by the net, not by an error

    def test_an_odd_cache_counts_as_none_and_loses_no_address(self):  # CISO #89
        for content in (b'{"ids": "x", "gh_logins": []}', b'{"ids": 7}', b'{"ids": [1, "masik@example.com"]}',
                        b'{"ids": [], "gh_logins": "y"}', b'[]'):
            with self.subTest(content=content):
                self.setUp()
                self.place("home:.claude.json", json.dumps({"oauthAccount": {"emailAddress": ADDR}}).encode())
                self.place("root:.mentat/identitas.json", content)
                decision, why = self.answer("WebFetch", {"url": OPENALEX, "prompt": "x"})
                self.assertEqual(decision, "ask", why)  # the account's address is still seen

    def test_the_suggestion_tool_survives_an_odd_manifest(self):
        import szerep_id_javaslat
        for content in SHAPES + [b'{"components": "x"}', b'{"components": {"brain": 5}}']:
            with self.subTest(content=content[:30]):
                (self.root / "mentat.json").write_bytes(content)
                (self.root / ".mentat").mkdir(exist_ok=True)
                (self.root / ".mentat" / "local.json").write_bytes(content)
                self.assertIsInstance(szerep_id_javaslat.suggest(self.root), list)


if __name__ == "__main__":
    sys.exit(unittest.main())
