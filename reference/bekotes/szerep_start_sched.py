"""SessionStart: the last scheduled run's state in front of the agent, before anything else.

note(data) -> text or None. Only where the engine is installed (mentat.json components.engine):
mentat_done_sched.lines() on the last run — fresh, not degraded, left its output. Silent when it
is all OK; any RED line goes into the session's context with the rule: fix it, check it again,
then tell the USER (in the brain's language). Never raises (the guard's session start must not fail on it).
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def note(data):
    try:
        root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
        doc = json.loads((root / "mentat.json").read_text(encoding="utf-8"))
        comp, lang = doc.get("components") or {}, (doc.get("agent") or {}).get("language")
        if not comp.get("engine"):
            return None
        for d in (HERE.parent, HERE.parent / "manifest"):  # .mentat/bin/ installed; reference/manifest/ dev
            if (d / "mentat_done_sched.py").is_file() and str(d) not in sys.path:
                sys.path.append(str(d))
        import mentat_done_sched as sched
        red = [ln for ln in sched.lines(root, 26, []) if ln.startswith("RED ")]
    except Exception:  # noqa: BLE001 — a note, never a failure
        return None
    if not red:
        return None
    if lang == "en":
        return ("Your scheduled run (mentat_done --scheduled): %s. Fix it first, check it again, then tell the USER "
                "in plain words what was wrong and that it works now." % " · ".join(red))
    return ("Az ütemezett futásod állapota (mentat_done --scheduled): %s. Előbb javítsd meg, ellenőrizd újra, aztán "
            "mondd el a FELHASZNÁLÓnak egyszerű szavakkal, mi volt a baj, és hogy most működik." % " · ".join(red))
