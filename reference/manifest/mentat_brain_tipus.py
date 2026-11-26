"""Owner-domain entity types: the definition file and how a note is checked against it.

A definition lives in the brain itself: <brain>/types/<slug>.md. Frontmatter (one source of truth):

    type: entity-type
    slug: bor                      # the notes' `type:` value
    name: Bor
    dir: borok                     # folder under the brain
    description: when to use it
    title_field: nev               # the frontmatter key holding the note's title (optional)
    due_field: kostolo             # a date field that `due` reports (optional)
    fields:
      - nev:text:required
      - szin:enum:required:enum=voros|feher|rose

The body is the skeleton of a new note ({t} = title, {d} = today).
"""
import re

import mentat_brain_types as bt

TYPES_DIR = "types"
KINDS = ("text", "date", "number", "enum", "link", "list")
# built-in or template-only note types, never a custom slug
RESERVED = set(bt.DIRS) | {"exploration", "specification", "procedure", "project", "subagent", "entity-type"}
BUILTIN_DIRS = set(bt.DIRS.values()) | {"explorations", "specs", "procedures", "subagents", "subagentek",
                                        "projects", TYPES_DIR}
DATE = re.compile(r"\d{4}-\d\d-\d\d(?:[ T]\d\d:\d\d)?$")


def parse_field(spec):
    """'szin:enum=a|b:required' (any order after the name) -> dict; ValueError if malformed."""
    parts = [s.strip() for s in spec.split(":")]
    if not parts[0] or bt.slugify(parts[0]).replace("-", "_") != parts[0]:
        raise ValueError("bad field name %r (lowercase a-z, 0-9, _)" % parts[0])
    f = {"name": parts[0], "kind": "text", "required": False, "enum": []}
    for p in parts[1:]:
        if p == "required":
            f["required"] = True
        elif p.startswith("enum="):
            f["kind"], f["enum"] = "enum", [v for v in p[5:].split("|") if v]
        elif p in KINDS:
            f["kind"] = p
        elif p:
            raise ValueError("bad field part %r in %r (kinds: %s)" % (p, spec, "|".join(KINDS)))
    if f["kind"] == "enum" and not f["enum"]:
        raise ValueError("enum field %r needs enum=a|b" % f["name"])
    return f


def field_spec(f):
    return ":".join([f["name"], f["kind"]] + (["required"] if f["required"] else []) +
                    (["enum=" + "|".join(f["enum"])] if f["kind"] == "enum" else []))


def describe(f):
    return "%s: %s%s%s" % (f["name"], f["kind"], " (%s)" % "|".join(f["enum"]) if f["enum"] else "",
                           ", required" if f["required"] else "")


def parse(text):
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return None
    head, body = text[4:].split("\n---", 1)
    d, fields = {}, []
    for ln in head.splitlines():
        m = re.match(r"\s+- (.+)$", ln)
        if m:
            fields.append(parse_field(m.group(1)))
            continue
        m = re.match(r"([a-z_]+):[ \t]*(.*)$", ln)
        if m:
            d[m.group(1)] = m.group(2).strip()
    if d.get("type") != "entity-type" or not d.get("slug"):
        return None
    d["fields"] = fields
    d["body"] = body.lstrip("\n").lstrip("\n") or "# {t}\n"
    return d


def render(d):
    rows = ["type: entity-type"] + ["%s: %s" % (k, d[k]) for k in
            ("slug", "name", "dir", "description", "title_field", "due_field") if d.get(k)]
    rows += ["fields:"] + ["  - " + field_spec(f) for f in d["fields"]]
    return "---\n" + "\n".join(rows) + "\n---\n\n" + (d.get("body") or "# {t}\n")


def load(root, brain):
    """slug -> definition, from <brain>/types/*.md (a broken file is skipped, never fatal)."""
    out = {}
    for p in sorted((root / brain / TYPES_DIR).glob("*.md")):
        try:
            d = parse(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = None
        if d:
            d["path"] = p
            out[d["slug"]] = d
    return out


def problems(fm, d):
    """What a note's frontmatter lacks or gets wrong against its type (list of short strings)."""
    out, missing = [], [f["name"] for f in d["fields"] if f["required"] and not fm.get(f["name"])]
    if missing:
        out.append("missing " + ", ".join(missing))
    for f in d["fields"]:
        v = (fm.get(f["name"]) or "").strip()
        if not v:
            continue
        if f["kind"] == "enum" and v not in f["enum"]:
            out.append("%s %r not in %s" % (f["name"], v, "|".join(f["enum"])))
        elif f["kind"] == "date" and not DATE.match(v):
            out.append("%s %r is not a date (YYYY-MM-DD)" % (f["name"], v))
        elif f["kind"] == "number" and not re.match(r"-?\d+(?:[.,]\d+)?$", v):
            out.append("%s %r is not a number" % (f["name"], v))
    return out
