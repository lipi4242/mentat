"""A `fleet ask` parancssora (a logika: ask.py).

  0 a válasz kész (utolsó sora KÉSZ) · 3 elküldve, a válasz még nincs kész (újra: --poll-only)
  1 hiba / nem írtam a pane-be (engedélyablak, lejárt login, nincs session)
"""
from __future__ import annotations
import getpass
import socket
import sys
import time
from pathlib import Path

from fleet import ask
from fleet.remote import resolve


def _answer_path(p: str | None) -> str | None:
    if p and p.startswith("~/"):
        return "$HOME/" + p[2:]
    return p


def cmd_ask(a) -> int:
    entry, tgt = resolve(a.agent, ssh=a.ssh)
    if entry is None and not a.ssh:
        print(f"{a.agent}: nincs a registryben — add meg a boxot: --ssh <user@box>", file=sys.stderr)
        return 1
    session = a.session or (entry or {}).get("session") or (entry or {}).get("agent") or a.agent
    if a.poll_only and not a.answer_path:
        print("--poll-only mellé kell az --answer-path (amit az első futás kiírt)", file=sys.stderr)
        return 1
    if not a.poll_only and not a.file:
        print("kell a --file (vagy --poll-only --answer-path)", file=sys.stderr)
        return 1
    text = "" if a.poll_only else Path(a.file).read_text(encoding="utf-8")
    if not a.poll_only and not text.strip():
        print(f"üres kérdésfájl: {a.file}", file=sys.stderr)
        return 1
    sender = a.sender or f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}"
    r = ask.ask(tgt, session, text, sender=sender, ask_id=time.strftime("%Y%m%d-%H%M%S"),
                answer_path=_answer_path(a.answer_path), send=not a.poll_only)
    if not r["ok"]:
        print("\n".join(r["notes"]), file=sys.stderr)
        return 1
    for n in r["notes"]:
        print(n, file=sys.stderr)
    if not a.poll_only:
        print(f"elküldve: {session} @ {tgt.label}; válasz ide: {r['answer_path']}", file=sys.stderr)
    done, answer = ask.wait_answer(tgt, r["answer_path"], a.wait, every=a.every)
    if done:
        print(answer, end="" if answer.endswith("\n") else "\n")
        return 0
    again = f"fleet ask {a.agent}" + (f" --ssh {a.ssh}" if a.ssh else "") + \
            f" --poll-only --answer-path {r['answer_path']} --wait 900"
    print(f"a válasz még nincs kész ({int(a.wait)} mp után)" + (" — eddig:\n" + answer if answer.strip() else "")
          + f"\nújra: `{again}`", file=sys.stderr)
    return 3


def add_parser(sub) -> None:
    x = sub.add_parser("ask", help="kérdésfájl egy ágensnek a boxán (ssh + tmux-mutató, Telegram/RC nélkül), "
                                   "válasz fájlban, KÉSZ-jelölőig várva (0 kész · 3 még nincs · 1 hiba)")
    x.add_argument("agent", metavar="ágens")
    x.add_argument("--file", help="a kérdések (markdown)")
    x.add_argument("--wait", type=float, default=900, metavar="MP", help="ennyit vár a KÉSZ sorra (alap: 900)")
    x.add_argument("--every", type=float, default=10, metavar="MP", help="pollozási köz (alap: 10)")
    x.add_argument("--answer-path", metavar="ÚT", help="a válaszfájl a boxon (alap: ~/.cache/fleet-ask/<id>/valasz.md)")
    x.add_argument("--poll-only", action="store_true", help="nem küld, csak a meglévő válaszfájlt várja")
    x.add_argument("--ssh", metavar="user@box", help="a box, ha az ágens nincs (ezen a gépen) a registryben")
    x.add_argument("--session", help="tmux-session (alap: a registry `session`-je, különben az ágens neve)")
    x.add_argument("--from", dest="sender", metavar="NÉV", help="a mutató címkéje (alap: user@gép)")
    x.set_defaults(fn=cmd_ask)
