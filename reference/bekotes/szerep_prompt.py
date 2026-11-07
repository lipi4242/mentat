#!/usr/bin/env python3
"""UserPromptSubmit hook: the USER's real messages, recorded where the agent cannot write.

    szerep_prompt.py   (JSON on stdin: prompt, session_id; nothing on stdout)

Appends {"at", "text"} to .mentat/state/user-said/<session>.jsonl (0600; the guard denies the
agent's writes there, szerep_kapu_final). A Telegram message arrives through the bridge as a
prompt too. Not recorded: a cross-session / teammate / task / system envelope; on a fleet agent
anything but the bridge line of a sender on its allowlist (TELEGRAM_ALLOWLIST_IDS in
~/.config/<agent>/telegram.env); undecidable = not recorded. mentat_final.py approve looks for
its code in what is recorded after the preview. Keeps the last MAX_LINES per session.
Any error: silent (it must never stop the USER's message).
"""
import json
import os
import pathlib
import re
import sys
import time

SAID = os.path.join(".mentat", "state", "user-said")
MAX_LINES = 200


ENVELOPES = ("<cross-session-message", "<teammate-message", "<task-notification", "<system-reminder")
LINE = re.compile(r" id=(\d+) \| chat=-?\d+ \| msg=\d+(?: \| reply_to=\d+)?(?: \| szerkesztett)?\]: ")


def owners(root):
    """A fleet agent's allowed senders: TELEGRAM_ALLOWLIST_IDS of its bridge (~/.config/<agent>/telegram.env);
    None = not a fleet agent; an empty set = cannot tell (nothing counts)."""
    fleet = pathlib.Path(root, ".claude", "fleet.json")
    if not fleet.exists():
        return None
    try:
        agent = json.loads(fleet.read_text(encoding="utf-8"))["agent"]
        env = pathlib.Path(os.path.expanduser("~/.config/%s/telegram.env" % agent)).read_text(encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    ids = next((ln.split("=", 1)[1] for ln in env.splitlines() if ln.strip().startswith("TELEGRAM_ALLOWLIST_IDS=")), "")
    return {i.strip().strip("'\"") for i in ids.split(",") if i.strip().strip("'\"").isdigit()}


def users_words(text, allowed):
    """What of a prompt is the USER's own words: nothing from an envelope; on a fleet agent only the text
    of a bridge line whose one header names an allowed sender (a second header in it = forged: nothing)."""
    if any(e in text for e in ENVELOPES):
        return []
    if allowed is None:
        return [text]
    out = []
    for line in text.splitlines():
        heads = list(LINE.finditer(line))
        if line.startswith("[Telegram inbound | ") and len(heads) == 1 and heads[0].group(1) in allowed \
                and "| reaction]" not in line[:heads[0].end()]:
            out.append(line[heads[0].end():])
    return out


def record(data, root):
    words = users_words(str(data.get("prompt") or "").strip(), owners(root))
    text = "\n".join(w for w in words if w.strip())
    if not text:
        return
    sid = "".join(c for c in str(data.get("session_id") or "x") if c.isalnum() or c in "-_") or "x"
    d = pathlib.Path(root, SAID)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    path = d / (sid + ".jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()[-(MAX_LINES - 1):] if path.exists() else []
    lines.append(json.dumps({"at": time.time(), "text": text[:4000]}, ensure_ascii=False))
    tmp = d / (".%s.%d.tmp" % (sid, os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def main():
    try:
        data = json.load(sys.stdin)
        record(data, os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
    except Exception:  # noqa: BLE001 — a record, never a block
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
