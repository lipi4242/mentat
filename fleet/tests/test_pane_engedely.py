"""Engedélykérő ablak az ágens pane-jében = PIROS a doctorban és a flotta-jelentésben, okkal.
Mérve: egy Claude Code-hook ([plugin:…]) jóváhagyást kért a headless pane-ben, a híd nem írt
bele (F-17), és a doctor közben csupa zöldet mutatott. Production code: pane_engedely, doctor,
flotta_report."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fleet import doctor, flotta_report, pane_engedely, tick_gate_inject  # noqa: E402

PRIVACY = "\n".join([
    "⏺ Bash(python3 scripts/draft.py)",
    " Hook tool.check requires confirmation for this command:",
    " This call's input holds your account email address, which may leave this",
    " machine. If nobody asked to send it, go on without it.",
    " [plugin:cc-plugin-privacy]",
    " Do you want to proceed?",
    " ❯ 1. Yes",
    "   2. No",
    " Esc to cancel · Tab to amend"])
BOXED = "\n".join([
    "╭────────────────────────────╮",
    "│ Bash command               │",
    "│   curl -H 'X: titok' x     │",
    "│ Do you want to proceed?    │",
    "│ ❯ 1. Yes                   │",
    "│   2. No                    │",
    "╰────────────────────────────╯"])


def fake_run(text, code=0):
    return lambda cmd: subprocess.CompletedProcess(cmd, code, text, "")


class Read(unittest.TestCase):
    def test_hook_dialog_reason(self):
        d = pane_engedely.read("régi kimenet\n" * 30 + PRIVACY)
        self.assertEqual(d["source"], "[plugin:cc-plugin-privacy]")
        self.assertEqual(d["why"], "This call's input holds your account email address, which may leave this machine.")
        self.assertEqual(d["options"], ["1. Yes", "2. No"])

    def test_boxed_dialog_title_only(self):
        d = pane_engedely.read(BOXED)
        self.assertEqual(d["source"], "Bash command")
        self.assertEqual(d["why"], "")
        self.assertNotIn("titok", pane_engedely.line(BOXED))

    def test_not_a_dialog(self):
        for t in (None, "", "⏺ Do you want to proceed? Megnézem.\n> ", "1. Yes\n2. No"):
            self.assertIsNone(pane_engedely.read(t))
            self.assertIsNone(pane_engedely.line(t))

    def test_line_names_reason_and_telegram_answer(self):
        x = pane_engedely.line(PRIVACY)
        self.assertTrue(x.startswith("engedélykérő ablak"), x)
        self.assertIn("[plugin:cc-plugin-privacy]", x)
        self.assertIn("/igen", x)
        self.assertIn("/nem", x)

    def test_same_detector_as_the_bridge(self):
        js = (ROOT / "bridge" / "lib" / "pane-guard.mjs").read_text(encoding="utf-8")
        q = re.search(r"const QUESTION = /(.+)/;", js).group(1)
        y = re.search(r"const YES_OPTION = /(.+)/m;", js).group(1)
        self.assertEqual(tick_gate_inject._QUESTION.pattern, q)
        self.assertEqual(tick_gate_inject._YES.pattern, y)
        self.assertEqual(tick_gate_inject.TAIL_LINES, int(re.search(r"TAIL_LINES = (\d+)", js).group(1)))


class Capture(unittest.TestCase):
    ENTRY = {"agent": "a", "session": "a", "supervision": "systemd"}

    def test_red_line_from_the_pane(self):
        self.assertIn("[plugin:cc-plugin-privacy]", pane_engedely.red_line(self.ENTRY, run=fake_run(PRIVACY)))

    def test_no_session_no_tmux_no_line(self):
        self.assertIsNone(pane_engedely.red_line(self.ENTRY, run=fake_run("", 1)))
        self.assertIsNone(pane_engedely.red_line({"agent": "a"}, run=fake_run(PRIVACY)))
        self.assertIsNone(pane_engedely.red_line({**self.ENTRY, "supervision": "none"}, run=fake_run(PRIVACY)))


class Doctor(unittest.TestCase):
    def test_essentials_red_carries_the_dialog(self):
        with mock.patch("fleet.essentials.probe", return_value={}), \
             mock.patch("fleet.essentials_env.send_failures", return_value=None), \
             mock.patch("fleet.kepesseg.check", return_value={"red": [], "unknown": [], "ok": []}), \
             mock.patch("fleet.pane_engedely.red_line", return_value="engedélykérő ablak áll a pane-ben — x"):
            r = doctor.essentials_for({"agent": "a", "session": "a"})
        self.assertIn("engedélykérő ablak áll a pane-ben — x", r["red"])

    def test_report_key(self):
        self.assertEqual(flotta_report.check_key("engedélykérő ablak áll a pane-ben — x"), "ablak")


if __name__ == "__main__":
    unittest.main()
