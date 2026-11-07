"""mentat_done.py --scheduled: did the scheduled job run AND leave its output (not just the timer).

lines(root, hours, outputs) -> ["OK …" | "RED …"]:
- the last scheduled tick (data/state/last-tick.json; the engine stamps it only after its
  executor finished) landed within `hours`;
- that tick was not degraded (data/state/last-summary.json "errors", a provider's error);
- when it planned work and delivers to a file (components.engine.delivery.channel = file, dir
  default data/outbox): an output file written for that tick, not empty; Telegram: a WARN, the
  arrival is checked on the USER's side;
- every --output PATH (an own job's file): there, not empty, and written for the last tick (or
  within `hours` without one);
- every --expect TEXT, and every text the schedule stored (engine setup --expect:
  components.engine.delivery.expect), is in the engine's output. Not whether it is right.
"""
import json
import pathlib
import time

SLACK = 15 * 60
FIX = (" — fix it now, do not just offer: `python3 -m anytime_engine.setup --doctor` names what is wrong, "
       "`setup --install` with the recorded settings repairs it; then run this check again")  # the output is written during the tick, before its stamp


def _json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stamp(t):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def _holds(p, expect):
    """The job's own promise (--expect): every text must be in the output; not whether it is right."""
    text = p.read_text(encoding="utf-8", errors="replace")
    return ["RED output %s lacks what the job promised: %r — say so to the USER" % (p.name, e) for e in expect if e not in text]


def _written(root, rel, since, expect=()):
    p = root / rel
    if not p.is_file() or p.stat().st_size == 0:
        return "RED output %s is %s" % (rel, "empty" if p.is_file() else "not there")
    if p.stat().st_mtime < since:
        return "RED output %s is from %s, older than the last run: this run left nothing" % (rel, _stamp(p.stat().st_mtime))
    return _holds(p, expect) or "OK output %s written %s" % (rel, _stamp(p.stat().st_mtime))


def _delivered(root, since, actions, expect=()):
    eng = ((_json(root / "mentat.json").get("components") or {}).get("engine") or {})
    cfg = eng.get("delivery") or {}
    if not actions:
        return []
    if cfg.get("channel", "file") == "telegram":
        return ["WARN it was sent to Telegram: ask the USER whether it arrived, do not assume it"]
    folder = root / str(cfg.get("dir") or "data/outbox")
    fresh = [p for p in folder.glob("*.md") if p.stat().st_mtime >= since and p.stat().st_size]
    if not fresh:
        return ["RED the last tick planned %d action(s) but left no output in %s since then"
                % (actions, folder.relative_to(root))]
    p = max(fresh, key=lambda f: f.stat().st_mtime)
    return _holds(p, expect) or ["OK the scheduled output %s (written %s)" % (p.relative_to(root), _stamp(p.stat().st_mtime))]


def _manual(root, after):
    """An output newer than the stale tick came from a manual run (the morning is once a day, so the
    next scheduled tick then plans nothing): say it, so the two facts do not look contradictory."""
    folder = root / "data" / "outbox"
    newer = [p for p in folder.glob("*.md") if p.stat().st_mtime > after + SLACK] if folder.is_dir() else []
    return ["NOTE a manual run left %s at %s; the schedule itself is still stopped" % (
        max(newer, key=lambda f: f.stat().st_mtime).name, _stamp(max(f.stat().st_mtime for f in newer)))] if newer else []


def lines(root, hours, outputs, expect=()):
    root = pathlib.Path(root)
    tick = root / "data" / "state" / "last-tick.json"
    out = []
    if not tick.is_file():
        out.append("RED the schedule has not run here yet (no scheduled tick): do not say it ran" + FIX)
        since = time.time() - hours * 3600
    else:
        at = tick.stat().st_mtime
        since = at - SLACK
        age = (time.time() - at) / 3600
        out.append("RED the last scheduled tick was %s (%.0f hours ago): it is not running now%s" % (_stamp(at), age, FIX)
                   if age > hours else "OK last scheduled tick %s" % _stamp(at))
        if age > hours:
            out += _manual(root, at)
        summary = _json(root / "data" / "state" / "last-summary.json")
        out += ["RED the last tick ran degraded: %s" % str(e)[:160] for e in summary.get("errors") or []]
        out += ["RED %s could not read %s: %s" % (a.get("concern"), k, str(v["error"])[:120])
                for a in summary.get("planned") or [] for k, v in (a.get("read") or {}).items()
                if isinstance(v, dict) and "error" in v]
        stored = ((_json(root / "mentat.json").get("components") or {}).get("engine") or {}).get("delivery") or {}
        promised = list(expect) + [e for e in stored.get("expect") or [] if isinstance(e, str) and e not in expect]
        out += _delivered(root, since, _json(tick).get("actions") or 0, promised)
    for rel in outputs:
        got = _written(root, rel, since, expect)
        out += got if isinstance(got, list) else [got]
    return out
