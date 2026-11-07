"""A technical step handed to the USER bounces back once (failure class: "run this command",
"edit this file" to a non-developer, when the agent could do it itself)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

STOP = pathlib.Path(__file__).resolve().parent / "szerep_stop.py"


def transcript(said, asked="Csináld meg a listát."):
    p = pathlib.Path(tempfile.mkdtemp()) / "t.jsonl"
    rows = [{"type": "user", "message": {"content": asked}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": said}]}}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return str(p)


def stop(said, asked="Csináld meg a listát.", active=False, cwd=None, path=None):
    data = {"transcript_path": path or transcript(said, asked), "stop_hook_active": active, "cwd": cwd or ""}
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    r = subprocess.run([sys.executable, "-I", str(STOP)], input=json.dumps(data), capture_output=True, text=True,
                       env=env)
    return json.loads(r.stdout) if r.stdout.strip() else None


class Handoff(unittest.TestCase):
    def test_a_command_or_file_edit_for_the_user_bounces_once(self):
        for said in ("Nyiss egy terminált, és futtasd: `npm install`", "Now run this command: pip install x",
                     "Open your terminal and paste it into the terminal.", "Szerkeszd a config.json fájlt."):
            out = stop(said)
            self.assertEqual((out or {}).get("decision"), "block", said)
            self.assertIn("csináld meg most", out["reason"])
        self.assertIsNone(stop("Now run this command: x", active=True), "never twice in a row")

    def test_a_plain_answer_a_human_step_or_an_asked_for_command_passes(self):
        for said in ("Kész: a lista 42 sort tartalmaz, a fájl: lista.csv.",
                     "Jelentkezz be a Cloudflare-be, és írd be a kulcsot ebbe az űrlapba: http://127.0.0.1:5000/x"):
            self.assertIsNone(stop(said), said)
        self.assertIsNone(stop("Futtasd: `git log -1`", asked="Milyen paranccsal nézem meg a commitot?"))

    def test_a_bridge_agent_is_skipped_it_answers_through_its_channel(self):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / ".claude").mkdir()
        self.assertEqual((stop("Now run this command: x", cwd=str(root)) or {}).get("decision"), "block")
        (root / ".claude" / "fleet.json").write_text("{}")
        self.assertIsNone(stop("Now run this command: x", cwd=str(root)))

    def test_only_the_end_of_a_long_transcript_is_read(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "t.jsonl"
        rows = [{"type": "user", "message": {"content": "Milyen paranccsal?"}}]
        rows += [{"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 6000}]}}] * 50
        rows += [{"type": "assistant", "message": {"content": [{"type": "text", "text": "Now run this command: y"}]}}]
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        out = stop("", path=str(p))  # the asked-for-a-command line is ~300 KB back: not read
        self.assertEqual((out or {}).get("decision"), "block")

    def test_a_broken_input_never_breaks_the_session(self):
        r = subprocess.run([sys.executable, "-I", str(STOP)], input="nem json", capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


    def turn(self, said, tools=(), earlier=()):
        p = pathlib.Path(tempfile.mkdtemp()) / "t.jsonl"
        use = lambda cmd: {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}
        rows = [use(c) for c in earlier] + [{"type": "user", "message": {"content": "Tedd ki a listát."}}]
        rows += [use(c) for c in tools]
        rows += [{"type": "assistant", "message": {"content": [{"type": "text", "text": said}]}}]
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
        return stop("", path=str(p))

    def test_a_done_claim_after_work_needs_a_done_check_first(self):
        out = self.turn("Kész: a lista élesben van.", tools=["npx wrangler deploy"])
        self.assertEqual((out or {}).get("decision"), "block")
        self.assertIn("mentat_done.py --url", out["reason"])  # the command to run, in one line
        self.assertIn("--scheduled", out["reason"])
        ok = self.turn("Kész: a lista élesben van.", tools=["npx wrangler deploy",
                                                           "python3 .mentat/bin/mentat_done.py --protected https://x"])
        self.assertIsNone(ok)
        self.assertIsNone(self.turn("Kész, itt a válasz a kérdésedre."), "no work this turn: nothing to verify")

    def test_the_bounce_sends_a_missing_capability_through_the_finder_first(self):
        out = stop("Now run this command: x")
        self.assertIn("where --find", out["reason"])


    def test_an_english_brain_gets_the_bounce_in_english(self):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "mentat.json").write_text(json.dumps({"agent": {"language": "en"}}))
        out = stop("Now run this command: x", cwd=str(root))
        self.assertIn("do it now", out["reason"])
        self.assertNotIn("FELHASZNÁLÓ", out["reason"])


if __name__ == "__main__":
    unittest.main()
