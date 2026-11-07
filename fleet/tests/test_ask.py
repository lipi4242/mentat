"""`fleet ask`: kérdésfájl ssh-n a boxra, egysoros mutató a tmux-pane-be, válasz fájlban KÉSZ-ig
(2026-10-29: a fogadó ágens másik Claude-fiókon futott, RC nélkül — csak ssh volt)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from fleet import ask, cli

IDLE = "╭──────╮\n│ >    │\n╰──────╯\n  ? for shortcuts\n"
PERM = "Bash command\n  rm -rf x\nDo you want to proceed?\n❯ 1. Yes\n  2. No\n"
LOGIN = "⎿  API Error: 401 · Please run /login\n> \n"
BUSY = "✻ Thinking… (12s · esc to interrupt)\n> \n"

# A hamis ssh: a "távoli" parancsot helyben futtatja a box tmp HOME-jában (a PRELUDE a
# ~/.local/bin-t a PATH elejére teszi, ott áll a hamis tmux).
SSH = """#!/bin/bash
while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done; shift; host="$1"; shift
echo "$host" >> "$FAKE_SCEN/hosts"
HOME="$FAKE_HOME" exec bash -c "$*"
"""
# A hamis tmux: a pane szövege a scen/pane fájl; a send-keys naplóz; ha a scen/answer létezik,
# az „ágens" a mutatóban megadott fájlba írja a választ (a KÉSZ-szel).
TMUX = r"""#!/bin/bash
echo "$*" >> "$FAKE_SCEN/tmux"
case "$1" in
  capture-pane) [ -f "$FAKE_SCEN/pane" ] && exec cat "$FAKE_SCEN/pane"; echo "can't find session" >&2; exit 1;;
  send-keys)
    if [ "$4" = "-l" ]; then
      printf '%s\n' "$5" >> "$FAKE_SCEN/sent"
      if [ -f "$FAKE_SCEN/answer" ]; then
        p=$(printf '%s' "$5" | sed -n 's/.*fájlba: \([^ ]*\) ;.*/\1/p'); cp "$FAKE_SCEN/answer" "$p"
      fi
    else echo "<$4>" >> "$FAKE_SCEN/sent"; fi;;
esac
"""


class Box:
    def __init__(self):
        self._t = tempfile.TemporaryDirectory()
        root = Path(self._t.name)
        self.home, self.scen = root / "box-home", root / "scen"
        b = self.home / ".local" / "bin"
        b.mkdir(parents=True); self.scen.mkdir()
        (b / "tmux").write_text(TMUX); (b / "tmux").chmod(0o755)
        self.ssh = root / "ssh"
        self.ssh.write_text(SSH); self.ssh.chmod(0o755)
        self.saved = {k: os.environ.get(k) for k in ("FLEET_SSH", "FAKE_SCEN", "FAKE_HOME")}
        os.environ.update(FLEET_SSH=str(self.ssh), FAKE_SCEN=str(self.scen), FAKE_HOME=str(self.home))

    def put(self, name, text):
        (self.scen / name).write_text(text)

    def read(self, name):
        p = self.scen / name
        return p.read_text() if p.exists() else ""

    def close(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self._t.cleanup()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestPure(unittest.TestCase):
    def test_pane_block(self):
        self.assertIsNone(ask.pane_block(IDLE))
        self.assertIsNone(ask.pane_block(BUSY))
        self.assertIn("engedélykérő", ask.pane_block(PERM))
        self.assertIn("login", ask.pane_block(LOGIN))
        self.assertIn("tmux-session", ask.pane_block(None))
        self.assertIn("workspace trust", ask.pane_block("Quick safety check\n1. Yes, I trust this folder"))

    def test_question_alone_in_output_is_not_a_dialog(self):
        self.assertIsNone(ask.pane_block("the agent wrote: Do you want to merge it?\n> \n"))

    def test_pointer_is_one_line_and_labelled(self):
        p = ask.pointer("kerdezo@mac", "/h/q.md", "/h/a.md")
        self.assertNotIn("\n", p)
        self.assertTrue(p.startswith("[kerdezo@mac üzenete, nem Telegram]"))
        self.assertIn("/h/a.md", p)
        self.assertIn(ask.DONE, p)

    def test_answer_done_needs_last_line(self):
        self.assertTrue(ask.answer_done("1. igen\n\nKÉSZ\n\n"))
        self.assertFalse(ask.answer_done("KÉSZ\nmég írok"))
        self.assertFalse(ask.answer_done(""))
        self.assertFalse(ask.answer_done(None))


class TestOverFakeSsh(unittest.TestCase):
    def setUp(self):
        self.box = Box()
        self.qf = Path(self.box.scen.parent / "kerdesek.md")
        self.qf.write_text("1. Mit csinálsz naponta?\n2. Mi él csak szokásként?\n")

    def tearDown(self):
        self.box.close()

    def test_happy_path_copies_injects_and_returns_answer(self):
        self.box.put("pane", IDLE)
        self.box.put("answer", "1. kiadás\n2. memória\nKÉSZ\n")
        code, out, err = run("ask", "vilma", "--ssh", "u@box", "--file", str(self.qf), "--from", "fejleszto",
                             "--wait", "5", "--every", "0.1")
        self.assertEqual(code, 0, err)
        self.assertIn("2. memória", out)
        sent = self.box.read("sent").splitlines()
        self.assertEqual(len(sent), 2, sent)                  # egy sor + egy Enter, semmi más
        self.assertTrue(sent[0].startswith("[fejleszto üzenete, nem Telegram]"))
        self.assertEqual(sent[1], "<Enter>")
        q = re.search(r"Kérdések: (\S+)", sent[0]).group(1)
        self.assertTrue(q.startswith(str(self.box.home)), q)  # a box HOME-ja, kibontva
        self.assertEqual(Path(q).read_text(), self.qf.read_text())
        self.assertEqual(Path(q).stat().st_mode & 0o777, 0o600)
        self.assertIn("-t =vilma:", self.box.read("tmux"))
        self.assertEqual(self.box.read("hosts").split()[0], "u@box")

    def test_refuses_on_permission_dialog_and_sends_nothing(self):
        self.box.put("pane", IDLE + PERM)
        code, _out, err = run("ask", "vilma", "--ssh", "u@box", "--file", str(self.qf), "--wait", "0")
        self.assertEqual(code, 1)
        self.assertIn("engedélykérő", err)
        self.assertEqual(self.box.read("sent"), "")
        self.assertFalse((self.box.home / ".cache").exists())  # a kérdésfájl se ment át

    def test_refuses_on_expired_login_and_missing_session(self):
        self.box.put("pane", LOGIN)
        self.assertEqual(run("ask", "v", "--ssh", "u@b", "--file", str(self.qf), "--wait", "0")[0], 1)
        (self.box.scen / "pane").unlink()
        code, _o, err = run("ask", "v", "--ssh", "u@b", "--file", str(self.qf), "--wait", "0")
        self.assertEqual(code, 1)
        self.assertIn("tmux-session", err)
        self.assertEqual(self.box.read("sent"), "")

    def test_timeout_returns_3_then_poll_only_collects(self):
        self.box.put("pane", BUSY)
        code, _o, err = run("ask", "v", "--ssh", "u@b", "--file", str(self.qf), "--wait", "0.2", "--every", "0.1")
        self.assertEqual(code, 3, err)
        self.assertIn("sorba áll", err)
        apath = re.search(r"--answer-path (\S+)", err).group(1)
        Path(apath).write_text("félig\n")
        self.assertEqual(run("ask", "v", "--ssh", "u@b", "--poll-only", "--answer-path", apath,
                             "--wait", "0")[0], 3)
        Path(apath).write_text("kész válasz\nKÉSZ\n")
        code, out, _e = run("ask", "v", "--ssh", "u@b", "--poll-only", "--answer-path", apath, "--wait", "0")
        self.assertEqual(code, 0)
        self.assertIn("kész válasz", out)
        self.assertEqual(len(self.box.read("sent").splitlines()), 2)   # a poll-only nem küldött újra

    def test_refuses_existing_answer_file(self):
        self.box.put("pane", IDLE)
        old = self.box.home / "regi.md"
        old.write_text("régi válasz\nKÉSZ\n")
        code, _o, err = run("ask", "v", "--ssh", "u@b", "--file", str(self.qf), "--answer-path", "~/regi.md",
                            "--wait", "0")
        self.assertEqual(code, 1)
        self.assertIn("VAN-MAR", err)
        self.assertEqual(self.box.read("sent"), "")


if __name__ == "__main__":
    unittest.main()
