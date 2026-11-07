#!/usr/bin/env python3
"""The capability log: which release changed which capability, and how.

    mentat_caplog.py check [--changelog COMPONENT=PATH ...]
    mentat_caplog.py render md --lang en|hu      # CAPABILITY-LOG.md / .hu.md
    mentat_caplog.py render json                 # the website's feed

The source is release/capability-log.json. Each change is one CHANGELOG bullet; the bullet
carries the change's id as `<!-- cap: <id> -->`, so a CHANGELOG line and the capabilities it
moved can always be traced to each other. Capability ids come from the curated catalog
(capabilities/*.json); the catalog says what a capability IS, the log says when it changed.
"""
import argparse
import json
import pathlib
import re
import sys

import mentat_caps_index as idx
from mentat_caplog_render import GROUPS, render_json, render_md  # noqa: F401  (re-exported)

HERE = pathlib.Path(__file__).resolve().parent
REL = HERE.parent.parent
LOG = REL / "capability-log.json"
KINDS = ("new", "extended", "improved", "removed")
COMPONENTS = {"brain", "engine", "fleet", "admin"}
MARK = re.compile(r"<!-- cap: ([a-z0-9][a-z0-9-]*) -->")


def load(path=LOG):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def bullets(changelog_text, version):
    """Top-level bullets of the `## <version>` section, each as one string."""
    out, inside, cur = [], False, None
    for line in changelog_text.splitlines():
        if line.startswith("## "):
            inside = (line[3:].split() or [""])[0] == version
            cur = None
            continue
        if not inside:
            continue
        if line.startswith("- "):
            cur = [line]
            out.append(cur)
        elif cur is not None and (line.startswith("  ") or not line.strip()):
            cur.append(line)
        else:
            cur = None
    return ["\n".join(b) for b in out]


def problems(log, catalog, changelogs):
    """Every reason the log cannot be trusted; empty = consistent."""
    found = []
    caps = {e["id"]: e for e in catalog}
    seen = set()
    for rel in log.get("releases", []):
        ver = rel.get("version", "?")
        for ch in rel.get("changes", []):
            cid = ch.get("id", "")
            where = "%s/%s" % (ver, cid)
            if not MARK.fullmatch("<!-- cap: %s -->" % cid):
                found.append("%s: id must be lower-case letters, digits and dashes" % where)
            if (ver, cid) in seen:
                found.append("%s: duplicate change id" % where)
            seen.add((ver, cid))
            if ch.get("component") not in COMPONENTS:
                found.append("%s: component must be one of %s" % (where, sorted(COMPONENTS)))
            for key in ("title", "summary"):
                if set(ch.get(key) or {}) != {"hu", "en"} or not all((ch.get(key) or {}).values()):
                    found.append("%s: %s needs non-empty hu and en" % (where, key))
            if not ch.get("capabilities"):
                found.append("%s: names no capability" % where)
            for c in ch.get("capabilities") or []:
                cap, kind = c.get("id"), c.get("change")
                if kind not in KINDS:
                    found.append("%s: %s: change must be one of %s" % (where, cap, KINDS))
                if cap not in caps:
                    if kind != "removed":
                        found.append("%s: %s is not in the catalog" % (where, cap))
                elif caps[cap].get("scope") != "public":
                    found.append("%s: %s is not public; the log is" % (where, cap))
                elif kind == "removed" and caps[cap].get("lifecycle") == "active":
                    found.append("%s: %s is removed here but still active in the catalog" % (where, cap))
        for comp, path in changelogs.items():
            want = {ch["id"] for ch in rel.get("changes", []) if ch.get("component") == comp}
            text = pathlib.Path(path).read_text(encoding="utf-8")
            if not re.search(r"^## %s(\s|$)" % re.escape(ver), text, re.M):
                if want:
                    found.append("%s CHANGELOG: no '## %s' section" % (comp, ver))
                continue
            marked = []
            for b in bullets(text, ver):
                ids = MARK.findall(b)
                if len(ids) != 1:
                    found.append("%s CHANGELOG %s: a bullet carries %d markers (one needed): %s"
                                 % (comp, ver, len(ids), b.splitlines()[0][:60]))
                marked += ids
            for cid in sorted(set(marked) - want):
                found.append("%s CHANGELOG %s: marker %s has no change in the log" % (comp, ver, cid))
            for cid in sorted(want - set(marked)):
                found.append("%s CHANGELOG %s: change %s has no bullet" % (comp, ver, cid))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check")
    chk.add_argument("--changelog", action="append", default=[], metavar="COMPONENT=PATH")
    rnd = sub.add_parser("render")
    rnd.add_argument("format", choices=("md", "json"))
    rnd.add_argument("--lang", choices=("en", "hu"), default="en")
    ap.add_argument("--log", default=str(LOG))
    a = ap.parse_args(argv)
    log, catalog = load(a.log), idx.catalog()
    if a.cmd == "render":
        sys.stdout.write(render_md(log, catalog, a.lang) + "\n" if a.format == "md" else render_json(log, catalog))
        return 0
    changelogs = {"brain": REL / "CHANGELOG.md"}
    changelogs.update(dict(c.split("=", 1) for c in a.changelog))
    found = problems(log, catalog, changelogs)
    for p in found:
        print("CAPLOG: " + p)
    print("capability log: %s" % ("OK" if not found else "%d problem(s)" % len(found)))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
