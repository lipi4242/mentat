"""The daily reconciliation, without a scheduler of its own: the day's first `where --find` or
`--map` compares every capability's state with the last snapshot (.mentat/state/
capability-index.json), says once what changed (new, gone, availability moved), and takes a new
snapshot. Within a day it says nothing and keeps the snapshot.
"""
import json
import pathlib
import time

SNAPSHOT = pathlib.Path(".mentat") / "state" / "capability-index.json"
DAY = 24 * 3600


def changes(root, states, now=None):
    """states: {id: availability}. Returns the change lines (maybe empty); updates the snapshot."""
    now = now or time.time()
    path = pathlib.Path(root) / SNAPSHOT
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        at, prev = float(old["at"]), dict(old["states"])
    except (OSError, ValueError, KeyError, TypeError):
        at, prev = None, None
    if at is not None and now - at < DAY:
        return []
    out = []
    if prev is not None:
        out += ["+ %s (%s)" % (i, states[i]) for i in sorted(set(states) - set(prev))]
        out += ["- %s" % i for i in sorted(set(prev) - set(states))]
        out += ["~ %s: %s → %s" % (i, prev[i], states[i]) for i in sorted(set(prev) & set(states))
                if prev[i] != states[i]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": now, "states": states}, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return out
