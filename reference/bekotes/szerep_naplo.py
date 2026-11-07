"""Log of outside reads and gate decisions: .mentat/naplo/kivuli.jsonl.

One JSON line per decision: time, tool, paths, decision, kind. Never content, never the
command text (it may hold a secret). The agent cannot write this file (szerep_dontes).
"""
import datetime
import json
import pathlib

LOG = ".mentat/naplo/kivuli.jsonl"


def write(root, tool, paths, decision, kind):
    line = {"ido": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "eszkoz": tool, "utak": [str(p) for p in paths], "dontes": decision, "miert": kind}
    try:
        path = pathlib.Path(root) / LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never decide the call
