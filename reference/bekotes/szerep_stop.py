#!/usr/bin/env python3
"""Stop hook: a technical step handed to the USER bounces back once (an accident net).

    szerep_stop.py   (Claude Code Stop hook: JSON on stdin, {"decision": "block", …} on stdout)

When the turn's last reply tells the USER to run a command, open a terminal or edit a file,
the agent is sent back once: do it yourself if you can; the USER only does what needs a human
(a login, a payment, a physical step, typing a secret into the hidden form). Not when the USER
asked for a command themselves, never twice in a row (stop_hook_active), never for a bridge agent
(.claude/fleet.json: it answers through its channel); only the last 256 KB is read. Any error: silent
pass — this net must never stop a session. Also once: a "done / it works" reply after work in this
turn with no mentat_done.py run in the session. Known limits: text patterns only (hu, en).
"""
import json
import os
import re
import sys

HANDOFF = [re.compile(p, re.I) for p in (
    r"\bopen (a|the|your) terminal\b", r"\b(paste|type|enter|run)\b[^.\n]{0,40}\binto (the|your|a) terminal\b",
    r"\b(you can|please|just|now) run\b", r"\brun (this|these|the following)( commands?)?\b",
    r"\b(edit|open) (the|your) `?[\w./-]+\.(json|toml|ya?ml|env|py|sh|ini|cfg|conf)`? file\b",
    r"\bfuttasd\b", r"\bfuttass\b", r"\bterminál(t|ba|ban)\b", r"\bparancssor(ba|ban)\b",
    r"\b(szerkeszd|nyisd meg|írd át) (a|az) `?[\w./-]+\.(json|toml|ya?ml|env|py|sh|ini|cfg|conf)`?")]
TAIL = 256 * 1024
ASKED = re.compile(r"\b(command|commands|terminal|script|paranc\w*|terminál\w*|szkript\w*)\b", re.I)
REASON = ("Az utolsó válaszod technikai lépést ad a FELHASZNÁLÓnak (%s). Ha meg tudod csinálni magad, "
          "csináld meg most, és csak az eredményt mondd el. Ha egy képesség hiányzik hozzá: előbb "
          "`python3 .mentat/bin/mentat_brain.py where --find \"<a lépés>\"`, és ha valóban nincs, kapcsold be "
          "vagy építsd meg a nyugtája szerint. A FELHASZNÁLÓra csak az marad, amihez ember kell (bejelentkezés, "
          "fizetés, fizikai teendő, titok beírása a rejtett űrlapba); ha így sem megy, mondd el egyszerűen, miért.")
DONE = re.compile(r"\b(kész|elkészült|elkészítettem|működik|sikerült|lefutott|élesben|done|it works|is live|"
                  r"finished|completed|all set|up and running|deployed)\b", re.I)
DONE_REASON = ("Kész-nek jelented (%s), de ebben a sessionben nem futott ellenőrzés. Futtasd most, egy sorban: "
               "`python3 .mentat/bin/mentat_done.py --url <a cím> | --protected <belépős cím> | --file <a fájl> | "
               "--scheduled`, és a verdiktjét mondd el (LOCAL ONLY / NOT VERIFIED: így).")
WORK = {"Bash", "Write", "Edit", "NotebookEdit", "MultiEdit"}
EN = {REASON: "Your last reply hands the USER a technical step (%s). If you can do it yourself, do it now and say only "
              "the result. If a capability is missing: first `python3 .mentat/bin/mentat_brain.py where --find \"<the "
              "step>\"`, and if it really is not there, enable or build it by its receipt. The USER keeps only what needs a "
              "person (signing in, paying, a physical step, typing a secret into the hidden form); if even that fails, "
              "say simply why.",
      DONE_REASON: "You call it done (%s), but no check ran in this session. Run it now, one line: `python3 "
                   ".mentat/bin/mentat_done.py --url <address> | --protected <signed-in address> | --file <file> | "
                   "--scheduled`, and say its verdict (LOCAL ONLY / NOT VERIFIED: say so)."}


def _text(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def last_two(path):
    """(the last assistant text, the last USER text, Bash commands in the tail, worked this turn)."""
    said = asked = None
    cmds, worked = [], False
    with open(path, "rb") as f:  # the end only: a long session must not slow the stop
        start = max(0, f.seek(0, 2) - TAIL)
        f.seek(start)
        lines = f.read().decode("utf-8", "replace").splitlines()[1 if start else 0:]  # a cut first line
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        kind, text = e.get("type"), _text(e) if isinstance(e, dict) else ""
        uses = [c for c in ((e.get("message") or {}).get("content") or []) if isinstance(c, dict)
                and c.get("type") == "tool_use"] if kind == "assistant" and not isinstance(
                    (e.get("message") or {}).get("content"), str) else []
        cmds += [str((u.get("input") or {}).get("command", "")) for u in uses if u.get("name") == "Bash"]
        worked = worked or (asked is None and any(u.get("name") in WORK for u in uses))
        if kind == "assistant" and said is None and text.strip():
            said = text
        elif kind == "user" and said is not None and text.strip() and asked is None:
            asked = text
    return said or "", asked or "", cmds, worked


def _lang(root):
    try:
        return "en" if (json.load(open(os.path.join(root, "mentat.json"), encoding="utf-8")).get("agent") or {}).get(
            "language") == "en" else "hu"
    except (OSError, ValueError, AttributeError):
        return "hu"


def decide(data):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "."
    if data.get("stop_hook_active") or os.path.exists(os.path.join(root, ".claude", "fleet.json")):
        return None  # a bridge agent answers through its channel (send.mjs), not this text
    reason = bounce(*last_two(data.get("transcript_path") or ""), lang=_lang(root))
    return {"decision": "block", "reason": reason} if reason else None


def bounce(said, asked, cmds, worked, lang="hu"):
    """The one reason to send a reply back (hand-off or an unchecked 'done'), or None.
    Also used on a bridge agent's outgoing message (szerep_kuldes, PreToolUse)."""
    hit = next((m.group(0) for p in HANDOFF for m in [p.search(said)] if m), None)
    pick = (lambda s: EN[s]) if lang == "en" else (lambda s: s)  # noqa: E731 — the brain's language
    if hit and not ASKED.search(asked):
        return pick(REASON) % hit
    claim = DONE.search(said)
    if claim and worked and not any("mentat_done.py" in c for c in cmds):
        return pick(DONE_REASON) % claim.group(0)
    return None


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 — a net: never break the session
        return 0
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
