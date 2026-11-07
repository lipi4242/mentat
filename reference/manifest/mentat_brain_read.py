"""Read side of mentat_brain.py: walk the notes, `due` (compact), `find`."""
import datetime
import re
import unicodedata

import mentat_brain_types as bt

CLOSED = {"done", "cancelled", "dropped", "superseded", "skipped", "decided"}
COMPACT = 8  # lines `due` prints without --full


def notes(root, brain):
    for p in sorted((root / brain).rglob("*.md")):
        if p.name == "_meta.md":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = {}
        if text.startswith("---\n") and "\n---" in text[4:]:
            head = text[4:].split("\n---", 1)[0]
            fm = dict(m.groups() for m in re.finditer(r"^([a-z_]+):[ \t]*(.*)$", head, re.M))
        t = fm.get("title") or fm.get("name") or fm.get("topic")
        if not t:
            m = re.search(r"^(?:# |\*\*[^*\n]+:\*\* )(.+)$", text, re.M)
            t = m.group(1) if m else p.stem
        yield p, fm, t.strip(), text


def deadline(fm):
    when = (fm.get("due_at") or fm.get("due") or "").split()[0:1]
    return when[0] if when and re.match(r"\d{4}-\d\d-\d\d$", when[0]) else ""


def at_time(fm):
    """The clock time after the date, if the deadline has one ("2026-10-22 09:30", "…T09:30")."""
    m = re.match(r"\d{4}-\d\d-\d\d[ T](\d\d:\d\d)", fm.get("due_at") or fm.get("due") or "")
    return m.group(1) if m else ""


def people(text, names):
    """Names of the person notes this note links to (people/<slug>.md)."""
    found = re.findall(r"people/([A-Za-z0-9_.-]+?)(?:\.md)?[)\]|\s]", text)
    return [names[s] for s in dict.fromkeys(found) if s in names]


def is_open(fm):
    return (fm.get("status") or "open").split()[0] not in CLOSED


def due(a, root, brain):
    today = bt.local_today(root)
    horizon = today + datetime.timedelta(days=a.days)
    rows, all_notes = [], list(notes(root, brain))
    names = {p.stem: (fm.get("name") or title) for p, fm, title, _ in all_notes if fm.get("type") == "person"}
    for p, fm, title, text in all_notes:
        if not is_open(fm) or "type" not in fm:
            continue
        when = deadline(fm)
        if when and when > horizon.isoformat():
            continue
        if not when and not (a.all and fm["type"] in ("todo", "case", "specification")):
            continue
        mark = "LEJART" if when and when < today.isoformat() else ("MA" if when == today.isoformat() else "")
        who = people(text, names)
        label = title + (" (" + ", ".join(who) + ")" if who else "")
        rows.append((when or "9999", at_time(fm), mark, fm["type"], label, p.relative_to(root)))
    lines = ["%-10s %-5s %-6s %-8s %s  %s" % (w if w != "9999" else "-", t, mark, kind, label, rel)
             for w, t, mark, kind, label, rel in sorted(rows)]
    if len(lines) > COMPACT and not a.full:
        lines = lines[:COMPACT - 1] + ["+%d more (due --full)" % (len(lines) - COMPACT + 1)]
    print("\n".join(lines) if lines else "nothing due in %d days" % a.days)
    return 0


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def find(a, root, brain):
    words, hits = [fold(w) for w in a.words], []
    for p, fm, title, text in notes(root, brain):
        low = fold(text + " " + p.name)
        if all(w in low for w in words):
            score = sum(fold(title + p.name).count(w) * 5 + low.count(w) for w in words)
            line = next((ln.strip() for ln in text.splitlines()
                         if ln.strip() != "---" and all(w in fold(ln) for w in words[:1])), title)
            when = deadline(fm) if is_open(fm) else ""
            hits.append((-score, str(p.relative_to(root)), line[:110] + (" [due %s]" % when if when else "")))
    for _, rel, line in sorted(hits)[:a.limit]:
        print("%s: %s" % (rel, line))
    print("%d hit(s)%s" % (len(hits), "" if len(hits) <= a.limit else ", showing %d (--limit)" % a.limit))
    return 0 if hits else 1
