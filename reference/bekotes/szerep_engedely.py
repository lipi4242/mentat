#!/usr/bin/env python3
"""The consent list: paths outside the working folder the USER approved (.mentat/engedelyek.json).

Written ONLY by the guard's PostToolUse hook, after a call the PreToolUse hook answered with
"ask" actually ran, i.e. after the USER approved it in Claude Code. The agent cannot write
it: the guard denies every Edit/Write/Bash touch of the file.

    python3 .mentat/bin/bekotes/szerep_engedely.py lista     show the approved paths
"""
import datetime
import json
import os
import pathlib
import sys

LIST = ".mentat/engedelyek.json"


def _read(root):
    try:
        data = json.loads((pathlib.Path(root) / LIST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("engedelyek") if isinstance(data, dict) else None
    return [e for e in items if isinstance(e, dict) and isinstance(e.get("ut"), str)] if isinstance(items, list) else []


def load(root):
    return _read(root)


def record(root, items, tool, sid=None):
    """items: [(path, op, folder_sweep)]; a folder sweep is kept for this session only."""
    entries = _read(root)
    have = {(e["ut"], e.get("muvelet"), e.get("session")) for e in entries}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for path, op, sweep in items:
        key = (path, op, sid if sweep else None)
        if key not in have:
            have.add(key)
            e = {"ut": path, "muvelet": op, "session": key[2], "eszkoz": tool, "ido": now,
                 "ki": "FELHASZNÁLÓ (Claude Code jóváhagyás)"}
            try:  # the file's identity, not its spelling (case-sensitive disks, renames)
                st = os.stat(path)
                e.update(dev=st.st_dev, ino=st.st_ino)
            except OSError:
                pass
            entries.append(e)
    path = pathlib.Path(root) / LIST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"engedelyek": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] != ["lista"]:
        print("használat: szerep_engedely.py lista", file=sys.stderr)
        return 2
    print("\n".join("%s  %s%s (%s)" % (e["ut"], e.get("muvelet"), " — csak ez a session" if e.get("session") else "",
                                         e.get("ido")) for e in _read(".")) or "(üres)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
