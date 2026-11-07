"""Write/inspect side of mentat_brain.py: `mv`, `commit`, `where`."""
import json
import os
import pathlib
import re
import subprocess
import time

import mentat_brain_types as bt


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _title_of(text):
    m = re.search(r"^(?:title|name|topic): *(.+)$", text.split("\n---", 1)[0], re.M)
    return m.group(1).strip() if m else ""


def mv(a, root, brain):
    base = root / brain
    old = root / a.old
    if not old.is_file():
        hits = [p for p in base.rglob(pathlib.Path(a.old).name) if p.is_file()]
        if len(hits) != 1:
            print("STOP %s: %s" % (a.old, "not found" if not hits else "ambiguous, give the path"))
            return 1
        old = hits[0]
    text = old.read_text(encoding="utf-8")
    if a.new:
        name = a.new if a.new.endswith(".md") else a.new + ".md"
        new = old.with_name(name) if "/" not in name else root / name
    elif a.title:
        date = re.match(r"\d{4}-\d\d-\d\d-", old.name)
        new = old.with_name((date.group(0) if date else "") + bt.slugify(a.title) + ".md")
    else:
        print("STOP give a new name or --title")
        return 1
    if new.exists() and new != old:
        print("STOP exists: %s" % new.relative_to(root))
        return 1
    old_title = _title_of(text) if a.title else ""
    link = re.compile(r"(?<![\w.-])%s(?![\w-])" % re.escape(old.name))
    changed = []
    for p in sorted(list(base.rglob("*.md")) + [root / "AGENTS.md"]):
        if not p.is_file():
            continue
        s = p.read_text(encoding="utf-8")
        t = link.sub(new.name, s)
        if old_title:
            t = t.replace(old_title, a.title)
        if t != s:
            changed.append((p, t))
    print("%s %s -> %s; %d file(s) rewritten" % ("would mv" if a.dry_run else "mv",
          old.relative_to(root), new.relative_to(root), len(changed)))
    if a.dry_run:
        return 0
    if _git(root, "mv", str(old), str(new)).returncode != 0:
        os.rename(old, new)
    for p, t in changed:
        (new if p == old else p).write_text(t, encoding="utf-8")
    return 0


def commit(a, root, brain):
    _git(root, "add", "-A", "--", brain)
    staged = _git(root, "diff", "--cached", "--name-only", "--", brain).stdout.split()
    secret = [f for f in staged if pathlib.Path(f).name.startswith(".env")]
    if secret:
        _git(root, "reset", "-q", "--", *secret)
        print("STOP .env is never committed: %s (unstaged it; add it to .gitignore)" % ", ".join(secret))
        return 1
    if not staged:
        print("nothing to commit in %s/" % brain)
        return 0
    r = _git(root, "commit", "-q", "-m", a.message)
    if r.returncode:
        print("STOP git: %s" % (r.stderr.strip().splitlines() or ["commit failed"])[-1])
        return 1
    print("committed %s (%d file(s))" % (_git(root, "rev-parse", "--short", "HEAD").stdout.strip(), len(staged)))
    return 0


def _json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _timer(names):
    try:
        out = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--no-legend"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for ln in out.splitlines():
        unit = next((w for w in ln.split() if w.endswith(".timer")), "")
        if "tick" in unit and (not names or any(n and n in unit for n in names)):
            return unit
    return ""


def where(a, root, brain, lang):
    if any(getattr(a, k, None) for k in ("find", "decide", "map", "probe", "export")):
        import mentat_caps
        return mentat_caps.main(a, root, brain, lang)
    hu = lang == "hu"
    none = "NINCS" if hu else "NONE"
    m, loc = _json(root / "mentat.json"), _json(root / ".mentat" / "local.json")
    comp = m.get("components") or {}
    ident = (loc.get("fleet") or {}).get("agent_id") or (m.get("agent") or {}).get("name") or ""
    n = sum(1 for p in (root / brain).rglob("*.md") if p.name != "_meta.md")
    print("agy: %s/ (%s) - %d %s; `mentat_brain.py due|find`" % (brain, lang, n, "jegyzet" if hu else "notes"))
    eng = comp.get("engine")
    if eng is None:
        print("motor: %s" % none)
    else:
        tick = root / "data" / "state" / "last-tick.json"
        age = ("%d min" % ((time.time() - tick.stat().st_mtime) // 60)) if tick.exists() else "?"
        print("motor: %s, %s: %s; %s: %s; last-tick.json: %s" % (
            eng.get("path", "anytime_engine"), "ütemező" if hu else "schedule", eng.get("schedule_owner", "engine"),
            "timer" if hu else "timer", _timer([ident]) or "?", age))
    fl = loc.get("fleet") or {}
    fid = fl.get("agent_id")
    print("%s: %s" % ("flotta" if hu else "fleet",
                      "%s@%s - `fleet doctor %s`" % (fid, fl.get("host", "?"), fid) if fid else none))
    url = (loc.get("admin") or {}).get("url")
    if not url:
        print("admin: %s" % none)
    else:
        d = next((c for c in (pathlib.Path.home() / "src/mentat/admin/worker", root / "../mentat-admin/worker",
                              root / "../src/mentat-admin/worker", pathlib.Path.home() / "src/mentat-admin/worker")
                  if c.is_dir()), None)  # the one Mentat clone first; then the pre-0.5.0 admin clones
        print("admin: %s; cases: %s%s" % (url, (m.get("cases") or {}).get("backend", "markdown"),
              "; `cd %s && npm run where`" % d.resolve() if d else ""))
    return 0
