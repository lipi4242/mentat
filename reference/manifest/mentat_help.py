#!/usr/bin/env python3
"""The /mentat help. The text is hand-written and versioned (mentat-help.<lang>.md next to this
file); this script only picks the language, puts one "who am I" line on top, and builds status.

    python3 mentat_help.py            # the help (the part before the first "== " section)
    python3 mentat_help.py todo       # switching on the todo and the backlog, step by step
    python3 mentat_help.py status     # role, todo, scheduler, next step (from mentat.json)

Stdlib, no network, no LLM. The same output serves /mentat and a Telegram /help.
"""
import datetime
import json
import os
import pathlib
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_statusline as sl  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
T = {"hu": {"who": "Ki vagyok", "todo": "Todo", "sched": "Ütemező", "next": "Következő lépés",
            "todo_on": "bekapcsolva (@%s)", "todo_on_nohandle": "bekapcsolva",
            "todo_off": "nincs bekapcsolva", "admin_only": "nincs bekapcsolva (az admin be van kötve, a todo nincs)",
            "no_engine": "nincs telepítve", "fleet": "a flotta ütemezi",
            "engine": "a motor ütemezi, utolsó ütemezett futás: %s", "engine_never": "a motor ütemezi, még nem futott",
            "go_todo": "a todo bekapcsolása: /mentat todo",
            "go_engine": "az ütemező: python3 -m anytime_engine.setup --tz <időzóna> --install (az engine GUIDE szerint)",
            "all_on": "minden alap be van kapcsolva; mondd el, mivel kezdjünk",
            "missing": "A súgó szövege hiányzik: %s (telepítsd újra az agy eszközeit)."},
     "en": {"who": "Who I am", "todo": "Todo", "sched": "Scheduler", "next": "Next step",
            "todo_on": "on (@%s)", "todo_on_nohandle": "on",
            "todo_off": "off", "admin_only": "off (the admin is connected, the todo is not)",
            "no_engine": "not installed", "fleet": "the fleet runs it",
            "engine": "the engine runs it, last scheduled run: %s", "engine_never": "the engine runs it, no run yet",
            "go_todo": "switch on the todo: /mentat todo",
            "go_engine": "the scheduler: python3 -m anytime_engine.setup --tz <timezone> --install (see the engine GUIDE)",
            "all_on": "the basics are all on; tell me what to start with",
            "missing": "The help text is missing: %s (reinstall the brain's tools)."}}


def _who(f):
    return " · ".join(x for x in (f["name"], "+".join(f["roles"]), f.get("fleet")) if x)


def _section(lang, name):
    path = HERE / ("mentat-help.%s.md" % lang)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return T[lang]["missing"] % path.name
    parts = ("\n" + text).split("\n== ")
    if name is None:
        return parts[0].strip()
    for p in parts[1:]:
        head, _, body = p.partition("\n")
        if head.strip() == name:
            return body.strip()
    return ""


def _todo(admin, t):
    if "todo" in (admin.get("plugins") or []):
        h = admin.get("todo_handle")
        return (t["todo_on"] % h if h else t["todo_on_nohandle"]), True
    return (t["admin_only"] if admin else t["todo_off"]), False


def _scheduler(engine, root, t):
    if not engine:
        return t["no_engine"], False
    if engine.get("schedule_owner") == "fleet":
        return t["fleet"], True
    tick = root / "data" / "state" / "last-tick.json"
    try:
        at = datetime.datetime.fromtimestamp(tick.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return t["engine_never"], True
    return t["engine"] % at, True


def status(f, root, manifest):
    t = T[f["lang"]]
    comp = manifest.get("components") if isinstance(manifest.get("components"), dict) else {}
    admin = comp.get("admin") if isinstance(comp.get("admin"), dict) else {}
    engine = comp.get("engine") if isinstance(comp.get("engine"), dict) else {}
    todo, todo_on = _todo(admin, t)
    sched, sched_on = _scheduler(engine, root, t)
    nxt = t["all_on"] if todo_on and sched_on else (t["go_todo"] if not todo_on else t["go_engine"])
    return "\n".join("%s: %s" % kv for kv in ((t["who"], _who(f)), (t["todo"], todo), (t["sched"], sched),
                                               (t["next"], nxt)))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = (argv[0] if argv else "").strip().lower()
    f = sl.facts({"cwd": os.getcwd()})
    root = sl._find_root(os.getcwd())
    if cmd == "status":
        print(status(f, root, sl._json(root / "mentat.json")))
    elif cmd == "todo":
        print(_section(f["lang"], "todo"))
    else:
        print(_who(f) + "\n\n" + _section(f["lang"], None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
