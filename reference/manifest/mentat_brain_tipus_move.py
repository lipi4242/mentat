"""Moving notes between type folders without breaking anything: links, indexes, the `type:` line.

A plan is a list of (old path, new path, new type slug). `apply` rewrites, in every brain note and
AGENTS.md, the links that name the old folder (`kovek/x.md`, `../kovek/x.md`, `agy/kovek/x.md`) and
the bare `x.md` links that only worked inside the old folder; moves the index lines between the
_meta.md files; and changes only the `type:` line of a moved note's frontmatter. Note text is never
dropped. Paths are pathlib, links are written with `/` on every OS.
"""
import os
import re
import subprocess

import mentat_brain_tipus_cmd as tc


def _git_mv(root, old, new):
    r = subprocess.run(["git", "-C", str(root), "mv", str(old), str(new)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        os.replace(old, new)


def retype(text, slug):
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return "---\ntype: %s\n---\n\n" % slug + text
    head, rest = text[4:].split("\n---", 1)
    if re.search(r"^type:", head, re.M):
        head = re.sub(r"^type:[ \t]*.*$", "type: %s" % slug, head, count=1, flags=re.M)
    else:
        head = "type: %s\n" % slug + head
    return "---\n" + head + "\n---" + rest


def rekey(text, old, new):
    """Rename one frontmatter key (`old:` -> `new:`), value and body untouched."""
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return text
    head, rest = text[4:].split("\n---", 1)
    return "---\n" + re.sub(r"^%s:" % re.escape(old), new + ":", head, count=1, flags=re.M) + "\n---" + rest


def check(plan, root):
    """'' or why the plan cannot run (a target exists, two notes land on one name)."""
    seen = set()
    for old, new, _ in plan:
        if new != old and (new.exists() or new in seen):
            return "STOP %s exists - rename one note first (`mv`)" % new.relative_to(root).as_posix()
        seen.add(new)
    return ""


def describe(plan, root):
    for old, new, slug in plan:
        verb = "mv" if new != old else "keep"
        print("  %s %s -> %s (type: %s)" % (verb, old.relative_to(root).as_posix(), new.relative_to(root).as_posix(), slug))


def _relink(text, src, dst, moves):
    """src/dst: the linking file's folder before/after the plan."""
    for old, new in moves:
        od, nd, name = old.parent.name, new.parent.name, old.name
        if od != nd:
            text = re.sub(r"(?<![\w-])%s/%s(?![\w-])" % (re.escape(od), re.escape(name)),
                          lambda m: "%s/%s" % (nd, name), text)
        if src == old.parent and dst != new.parent:  # a bare link only worked next to it
            text = re.sub(r"(?<=\]\()%s(?=\))" % re.escape(name), lambda m: "../%s/%s" % (nd, name), text)
    return text


def apply(plan, root, brain):
    """Run the plan (check() first). Returns the number of other files whose links changed."""
    moves = [(o, n) for o, n, _ in plan if o != n]
    moved = {o: n for o, n in moves}
    changed = 0
    for p in sorted(list((root / brain).rglob("*.md")) + [root / "AGENTS.md"]):
        if not p.is_file() or p in moved:
            continue
        s = p.read_text(encoding="utf-8")
        t = _relink(s, p.parent, p.parent, moves)
        if p.name == "_meta.md":  # the moved notes' index lines go with them
            t = "".join(ln for ln in t.splitlines(True)
                        if not any(o.parent == p.parent and "](%s)" % o.name in ln for o in moved))
        if t != s:
            p.write_bytes((t).encode("utf-8"))
            changed += 1
    for old, new, slug in plan:
        t = _relink(old.read_text(encoding="utf-8"), old.parent, new.parent, moves)
        if new.parent != old.parent:  # its bare links to notes left behind now need the folder
            for q in old.parent.glob("*.md"):
                if q not in moved and q.name != "_meta.md":
                    t = re.sub(r"(?<=\]\()%s(?=\))" % re.escape(q.name), "../%s/%s" % (q.parent.name, q.name), t)
        t = retype(t, slug)
        if new != old:
            new.parent.mkdir(parents=True, exist_ok=True)
            _git_mv(root, old, new)
            title = re.search(r"^(?:title|name|nev|cim|megnevezes|topic): *(.+)$", t, re.M)
            tc.index(new.parent, root, "- [%s](%s) - %s\n" % (title.group(1).strip() if title else new.stem,
                                                               new.name, slug))
        new.write_bytes((t).encode("utf-8"))
    return changed
