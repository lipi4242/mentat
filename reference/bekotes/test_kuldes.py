"""A bridge agent's outgoing message gets the same two checks as a final reply (failure class:
fleet/Telegram agents skip the Stop hook, so a hand-off or an unchecked 'done' went out unseen).
Denied once with the bounce message, then the next send goes through; --react is untouched."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import tempfile
import unittest

from test_guard_kint import KintBase

SEND = 'node tools/send.mjs --chat 1 -- "%s"'


class Kuldes(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.root / ".claude").mkdir(exist_ok=True)
        (self.root / ".claude" / "fleet.json").write_text("{}")
        self.tr = pathlib.Path(tempfile.mkdtemp()) / "t.jsonl"
        rows = [{"type": "user", "message": {"content": "Tedd ki a listát."}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                                               "input": {"command": "npx wrangler deploy"}}]}}]
        self.tr.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def send(self, cmd, mode="bypassPermissions"):
        p = self.payload("Bash", {"command": cmd}, mode)
        p["transcript_path"] = str(self.tr)
        r = self.run_guard(p, None)
        out = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else {}
        return out.get("permissionDecision", "allow"), out.get("permissionDecisionReason", "")

    def test_a_handoff_or_unchecked_done_bounces_once_then_goes(self):
        d, why = self.send(SEND % "Nyiss egy terminált, és futtasd: npm install")
        self.assertEqual(d, "deny")
        self.assertIn("csináld meg most", why)
        self.assertEqual(self.send(SEND % "Nyiss egy terminált, és futtasd: npm install")[0], "allow", "once only")

    def test_done_without_a_check_bounces(self):
        d, why = self.send(SEND % "Kész, a lista élesben van!")
        self.assertEqual(d, "deny")
        self.assertIn("mentat_done.py", why)

    def test_plain_messages_reactions_and_other_agents_pass(self):
        self.assertEqual(self.send(SEND % "Megnéztem, 12 sor van benne.")[0], "allow")
        self.assertEqual(self.send("node send.mjs --chat 1 --react '👍' --message 5")[0], "allow")
        (self.root / ".claude" / "fleet.json").unlink()
        self.assertEqual(self.send(SEND % "Kész, a lista élesben van!")[0], "allow", "not a bridge agent")


class RealLayout(Kuldes):
    """As on the fleet: the bridge in ~/.config/<agent>/sub-etha/, the token sourced from there."""

    def setUp(self):
        super().setUp()
        (self.root / ".claude" / "fleet.json").write_text(json.dumps({"agent": "media-agent"}))
        cfg = self.home / ".config" / "media-agent"
        (cfg / "sub-etha").mkdir(parents=True)
        (cfg / "sub-etha" / "send.mjs").write_text("// send\n")
        (cfg / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=x\n")

    def test_the_documented_send_is_open_and_still_checked(self):
        src = "set -a; . ~/.config/media-agent/telegram.env; set +a; "
        real = src + 'node ~/.config/media-agent/sub-etha/send.mjs --chat 1 -- "%s"'
        self.assertEqual(self.send(src.strip())[0], "allow")
        self.assertEqual(self.send(src + "node ~/.config/media-agent/sub-etha/send.mjs --chat 1 --react 'x' --message 5")[0], "allow")
        self.assertEqual(self.send(real % "Megnéztem, 12 sor van benne.")[0], "allow")
        self.assertEqual(self.send(real % "Kész, a lista élesben van!")[0], "deny")
        self.assertEqual(self.send(real % "Kész, a lista élesben van!")[0], "allow", "once only")

    def test_without_a_readable_transcript_the_handoff_is_still_caught(self):
        self.tr = pathlib.Path("/nonexistent/t.jsonl")
        real = 'node ~/.config/media-agent/sub-etha/send.mjs --chat 1 -- "%s"'
        self.assertEqual(self.send(real % "Nyiss egy terminált, és futtasd: npm install")[0], "deny")
        self.assertEqual(self.send(real % "Kész!")[0], "allow", "a done-claim needs the transcript: open")


if __name__ == "__main__":
    unittest.main()
