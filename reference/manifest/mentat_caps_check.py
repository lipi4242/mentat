"""Capability-specific checks with a TTL: the expensive, real test of a capability (a token is
valid, the Google sign-in works, the vendored engine is intact), run only on
`where --probe ID|all` and remembered in .mentat/state/capability-checks.json.

The catalog names the check (`check: {"cmd": "...", "ttl_hours": N}`); only the shipped catalog
does, so `--probe` never runs an agent-written command. `--find` reads the remembered result:
a fresh failed check makes an `on` capability `degraded`; an old one is shown as stale and
decides nothing. A check's output is cut to its first line (the tools never print a secret).
"""
import json
import pathlib
import shlex
import subprocess
import time

STATE = pathlib.Path(".mentat") / "state" / "capability-checks.json"


def load(root):
    try:
        doc = json.loads((pathlib.Path(root) / STATE).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def run(root, entry):
    """Run one entry's check now; remember and return the result."""
    chk = entry["check"]
    try:
        r = subprocess.run(shlex.split(chk["cmd"]), cwd=str(root), capture_output=True, text=True, timeout=60)
        code, text = r.returncode, (r.stdout.strip() or r.stderr.strip())
    except (OSError, subprocess.SubprocessError) as e:
        code, text = 127, "could not run: %s" % type(e).__name__
    res = {"ok": code == 0, "exit": code, "line": (text.splitlines() or [""])[0][:160], "at": time.time(),
           "cmd": chk["cmd"]}
    doc = load(root)
    doc[entry["id"]] = res
    path = pathlib.Path(root) / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def annotate(view, entry, checks, now=None):
    """Add `verified` to a capability view; a fresh failure turns on into degraded."""
    res = checks.get(entry["id"]) if entry.get("check") else None
    if not res:
        view["verified"] = None
        return view
    ttl = float(entry["check"].get("ttl_hours", 24)) * 3600
    stale = (now or time.time()) - float(res.get("at", 0)) > ttl
    view["verified"] = {"ok": bool(res.get("ok")), "stale": stale, "line": res.get("line", ""),
                        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(res.get("at", 0))))}
    if not stale and not res.get("ok") and view.get("availability") == "on":
        view["availability"] = "degraded"
        view["probe"] = "%s; check failed: %s" % (view.get("probe", ""), res.get("line", ""))
    return view
