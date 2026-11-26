"""Engedélykérő ablak az ágens pane-jében: PIROS a doctorban és a flotta-jelentésben, okkal.

A felismerés a híd szabálya (bridge/lib/pane-guard.mjs, a Python-tükre tick_gate_inject.py: a
„Do you want to …?” kérdés ÉS az „1. Yes” sor együtt, a pane alján). Az ok kiolvasása a
bridge/lib/pane-dialog.mjs-é: a hook-sor („Hook … requires confirmation”), a [plugin:…] jelölő
és az első magyarázó mondat; keretes ablaknál csak a cím, a parancs törzse nem (titok is lehet).

Egy Claude Code-hook a skip-permissions mellett is kérhet jóváhagyást, a headless ágens addig
áll, a processz és a csatorna közben zöld. A tulajdonos Telegramon válaszolhat (/igen, /nem).
"""
from __future__ import annotations
import re

from fleet import pane
from fleet.tick_gate_inject import TAIL_LINES, _QUESTION, permission_dialog
from fleet.txn import run_cmd

_OPTION = re.compile(r"^(?:❯\s*)?(\d)\.\s+(.+)$")
_HOOK = re.compile(r"^Hook\b.*\brequires confirmation\b")
_PLUGIN = re.compile(r"\[plugin:[^\]\s]{1,80}\]")
_HEAD_MAX = 12


def _strip(line: str) -> str:
    return re.sub(r"[\s│|╮╯─]+$", "", re.sub(r"^[\s│|╭╰─]+", "", line))


def _clip(s: str, n: int = 200) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _sentence(lines: list[str]) -> str:
    t = re.sub(r"\s+", " ", " ".join(lines)).strip()
    m = re.match(r"^.*?[.!?](?=\s|$)", t)
    return _clip(m.group(0) if m else t)


def read(text: str | None) -> dict | None:
    """Pure: {source, why, question, options}, ha a pane alján engedélykérő ablak áll; különben None."""
    if not permission_dialog(text):
        return None
    lines = [_strip(x) for x in text.rstrip().split("\n")[-TAIL_LINES:]]
    q = max((i for i, x in enumerate(lines) if _QUESTION.search(x)), default=-1)
    if q < 0:
        return None
    options = []
    for x in lines[q + 1:]:
        m = _OPTION.match(x)
        if m:
            options.append(f"{m.group(1)}. {_clip(m.group(2).strip(), 80)}")
        elif options:
            break
    s = q
    while s > 0 and lines[s - 1] and q - s < _HEAD_MAX:
        s -= 1
    head = lines[s:q]
    hi = next((i for i, x in enumerate(head) if _HOOK.search(x)), -1)
    plugin = _PLUGIN.search(" ".join(head))
    why = _sentence([x for x in head[hi + 1:] if not _PLUGIN.search(x)]) if hi >= 0 else ""
    source = (plugin.group(0) if plugin else "") or (_clip(head[hi]) if hi >= 0 else "") \
        or _clip(next((x for x in head if x), ""), 120)
    return {"source": source, "why": why, "question": _clip(lines[q]), "options": options}


def line(text: str | None) -> str | None:
    """Pure: a piros sor, vagy None."""
    d = read(text)
    if d is None:
        return None
    why = f" — {d['why']}" if d["why"] else ""
    return (f"engedélykérő ablak áll a pane-ben, az ágens nem dolgozik: {d['source']}{why} "
            f"({' · '.join(d['options'])}); a tulajdonos Telegramon válaszolhat: /igen vagy /nem")


def red_line(entry: dict, run=run_cmd) -> str | None:
    """A felügyelt ágens pane-jéből; nincs session / tmux / ablak = None (azt más jel méri)."""
    if not entry.get("session") or entry.get("supervision") == "none":
        return None
    return line(pane.capture(entry["session"], run))
