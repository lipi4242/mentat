"""A bridge agent's outgoing message (send.mjs -- "text") gets the Stop hook's two checks.

check(data, root) -> deny reason or None (szerep_dontes, PreToolUse). Only with
.claude/fleet.json (the agent answers through its channel, so the Stop hook skips it), only a
Bash call of send.mjs with a text after `--` (a --react alone is untouched). The text goes
through szerep_stop.bounce (a hand-off, or "done" after work with no mentat_done.py run). One
bounce per USER message: the receipt in .mentat/state/send-bounce/ holds that message's hash,
and the next send goes through. Any error: None (fail open, never blocks a reply).
"""
import hashlib
import json
import os
import pathlib

import szerep_stop
from szerep_bash import commands

STATE = os.path.join(".mentat", "state", "send-bounce")


def _text(cmd, cwd):
    for _n, words, _wd, _r, _a in commands(cmd, cwd):
        if any(os.path.basename(w) == "send.mjs" for w in words) and "--" in words:
            return " ".join(words[words.index("--") + 1:]).strip()
    return ""


def check(data, root):
    try:
        if data.get("tool_name") != "Bash" or not os.path.exists(os.path.join(root, ".claude", "fleet.json")):
            return None
        text = _text(str((data.get("tool_input") or {}).get("command", "")), data.get("cwd") or str(root))
        if not text:
            return None
        try:
            _said, asked, cmds, worked = szerep_stop.last_two(data.get("transcript_path") or "")
        except OSError:  # no transcript: the hand-off check still runs, a done-claim cannot be judged
            asked, cmds, worked = "", [], False
        lang = szerep_stop._lang(str(root))
        reason = szerep_stop.bounce(text, asked, cmds, worked, lang)
        if not reason:
            return None
        mark = pathlib.Path(root, STATE, "".join(c for c in str(data.get("session_id") or "x") if c.isalnum() or c in "-_"))
        turn = hashlib.sha256(asked.encode("utf-8")).hexdigest()
        if mark.is_file() and mark.read_text(encoding="utf-8").strip() == turn:
            return None  # bounced once for this USER message: let it go
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(turn, encoding="utf-8")
        return reason + (" (The message was not sent: rewrite it and send again.)" if lang == "en"
                         else " (Az üzenet nem ment el; írd át, és küldd újra.)")
    except Exception:  # noqa: BLE001 — a net: never block a reply on its own error
        return None
