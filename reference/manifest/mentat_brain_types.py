"""What `mentat_brain.py new` writes: frontmatter and body skeleton per note type.

Mirrors reference/templates/<type>.<lang>.md - change both together.
"""
import datetime
import json
import os
import pathlib
import re
import time
import unicodedata

DIRS = {"brain-dump": "brain-dumps", "person": "people", "todo": "todos",
        "decision": "decisions", "case": "cases", "connector": "connectors"}
DATED = ("brain-dump", "decision")
# (label of the first body line, rest of the body); {t} = the title
BODY = {
    "hu": {"brain-dump": ("# {t}\n\n", "\n"),
           "person": ("**Ki ő:** {t}", "\n\n**Kapcsolat a tulajjal:** \n\n**Ami fontos:** \n"),
           "todo": ("**Feladat:** {t}", "\n\n**Kontextus:** \n\n**A \"kész\" definíciója:**\n- \n"),
           "decision": ("**Döntés:** {t}", "\n\n**Miért:** \n\n**Linkek:** \n"),
           "case": ("**Kontextus:** {t}", "\n\n**Napló:**\n- {d} — létrehozva.\n"),
           "connector": ("**Mihez kapcsolódik:** {t}",
                         "\n\n**Hitelesítés + beállítás:** csak `.env` kulcsnevek, érték soha.\n\n"
                         "**Elérhető műveletek:**\n- \n\n**Furcsaságok / ismert korlátok:** \n")},
    "en": {"brain-dump": ("# {t}\n\n", "\n"),
           "person": ("**Who:** {t}", "\n\n**Relationship to the owner:** \n\n**What matters:** \n"),
           "todo": ("**Task:** {t}", "\n\n**Context:** \n\n**Definition of done:**\n- \n"),
           "decision": ("**Decision:** {t}", "\n\n**Why:** \n\n**Links:** \n"),
           "case": ("**Context:** {t}", "\n\n**Log:**\n- {d} - created.\n"),
           "connector": ("**Connects to:** {t}",
                         "\n\n**Auth + setup:** `.env` key names only, never values.\n\n"
                         "**Available operations:**\n- \n\n**Quirks / known limits:** \n")},
}


def local_today(root=".", now=None):
    """Today in the agent's own timezone (ANYTIME_TZ, else mentat.json
    components.engine.timezone, else the machine's local time) - never the box's UTC day."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    name = os.environ.get("ANYTIME_TZ")
    if not name:
        try:
            doc = json.loads((pathlib.Path(root) / "mentat.json").read_text(encoding="utf-8"))
            name = ((doc.get("components") or {}).get("engine") or {}).get("timezone")
        except (OSError, ValueError, AttributeError):
            name = None
    if not name:
        return now.astimezone().date()
    import zoneinfo
    try:
        return now.astimezone(zoneinfo.ZoneInfo(name)).date()
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        raise SystemExit("STOP unknown timezone %r (an IANA name like Europe/Budapest; "
                         "fix components.engine.timezone in mentat.json)" % name)


def slugify(text):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "untitled"


def ulid():
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    a = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return "".join(a[(n >> 5 * i) & 31] for i in range(25, -1, -1))


def frontmatter(kind, title, tags, due, today=None):
    today = today or datetime.date.today().isoformat()
    tg = "tags: [%s]" % ", ".join(tags)
    due_line = ["due: %s" % due] if due else []
    rows = {
        "todo": ["type: todo", "status: open", "priority: med"] + due_line,
        "decision": ["type: decision", "date: %s" % today, "status: decided", "weight: normal"],
        "person": ["type: person", "name: %s" % title, "role: ", "relationship: colleague"],
        "connector": ["type: connector", "name: %s" % slugify(title), "status: placeholder",
                      "auth_location: .env"],
        "brain-dump": ["type: brain-dump", "date: %s" % today, "topic: %s" % slugify(title),
                       "processed: false"],
        "case": ["type: case", "case_id: %s" % ulid(), "title: %s" % title, "status: open",
                 "description: ", "next_action: "] + (["due_at: %s" % due] if due else []),
    }[kind]
    return "---\n" + "\n".join(rows + [tg]) + "\n---\n\n"
