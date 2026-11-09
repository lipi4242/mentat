"""A tick-parancs beküldése a pane-be — ugyanaz a mechanika és ugyanazok az őrök, mint a hídé
(fleet/bridge/lib/inject.mjs, pane-guard.mjs) és az agent-startup-seed.sh-é.

- `send-keys -l --` szó szerinti szöveg, a sor lezárása KÜLÖN `Enter`; cél: `=<session>:`
  (a tmux 3.6 a csupasz `=név`-et nem oldja fel);
- engedélykérő ablaknál (a híd mintái) és indítási ablaknál (pane.DIALOGS) semmi nem megy ki;
- foglalt az ágens, ha a transzkript friss, vagy a pane alján fut egy kör: akkor sem küldünk.
A beküldött szöveg mindig a registry `tick_cmd`-je (render._SAFE_CMD), sosem külső adat.
"""
from __future__ import annotations

import re

from fleet import pane
from fleet.txn import run_cmd

TAIL_LINES = 40
_QUESTION = re.compile(r"Do you want to [^\n]{0,200}\?")
_YES = re.compile(r"^[\s│|]*(?:❯\s*)?1\.\s+Yes\b", re.M)
_RUNNING = ("esc to interrupt",)
#: a kész prompt jele (ugyanaz, amire az agent-startup-seed.sh vár): enélkül nem claude-prompt
#: van a pane-ben (boot-képernyő, shell) — oda egy Enter vakon menne (Codex, 11-08)
READY = "bypass permissions"


def _tail(text: str) -> str:
    return "\n".join(text.split("\n")[-TAIL_LINES:])


def permission_dialog(text: str | None) -> bool:
    """Pure: a híd pane-guard.mjs szabálya (kérdés ÉS „1. Yes” együtt, a pane alján)."""
    if not text:
        return False
    t = _tail(text)
    return bool(_QUESTION.search(t) and _YES.search(t))


def pane_busy(text: str | None) -> str | None:
    """Pure: miért NEM küldhető most be semmi (None = küldhető)."""
    if text is None:
        return "a pane nem olvasható (nincs session?)"
    if permission_dialog(text):
        return "engedélykérő ablak áll a pane-ben"
    d = pane.dialog_in(text)
    if d:
        return f"a claude a(z) „{d[0]}” ablaknál áll"
    if any(m in _tail(text) for m in _RUNNING):
        return "az ágens éppen dolgozik (fut egy kör)"
    if READY not in _tail(text):
        return "a claude promptja nem látszik a pane-ben (boot vagy nem claude)"
    return None


def transcript_busy(age_s: float | None, fresh_s: float) -> str | None:
    if age_s is not None and age_s < fresh_s:
        return f"a transzkript {int(age_s)} mp-e íródott (dolgozik)"
    return None


def send(session: str, line: str, run=run_cmd, tmux: str = "tmux") -> tuple[bool, str]:
    """(siker, ok). Előbb újra megnézi a pane-t: két olvasás közt is felugorhat egy ablak."""
    why = pane_busy(pane.capture(session, run, tmux))
    if why:
        return False, why
    target = f"={session}:"
    a = run([tmux, "send-keys", "-t", target, "-l", "--", line])
    if a.returncode:
        return False, f"send-keys (szöveg) kód {a.returncode}"
    b = run([tmux, "send-keys", "-t", target, "Enter"])
    if b.returncode:
        return False, f"send-keys (Enter) kód {b.returncode}"
    return True, "beküldve"
