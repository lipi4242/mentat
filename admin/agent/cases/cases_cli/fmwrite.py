"""Writing a case file's frontmatter without disturbing the rest of it.

Only the named top-level keys are replaced (or removed, or appended); every
other key, its comments and the body stay byte for byte. The output is the
YAML subset frontmatter.py (the engine's parser) reads back.
"""
import re

from common import CasesError

DELETE = object()
_PLAIN = re.compile(r"^[^\s\"'\[\]{}#&*!|>%@`,:-][^#]*$")
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def split(text):
    """(frontmatter lines, body) — body is everything after the closing ---."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    raise CasesError("frontmatter not closed with ---")


def context(text):
    return split(text)[1].lstrip("\n")


def scalar(v, flow=False):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (_key(k), scalar(x, True)) for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(scalar(x, True) for x in v) + "]"
    s = str(v)
    if "\n" in s:
        raise CasesError("a frontmatter value cannot span lines: %r" % s[:40])
    risky = (not _PLAIN.match(s) or s != s.strip() or s in ("null", "~", "true", "false")
             or s.lstrip("-").isdigit() or ": " in s or s.endswith(":")
             or (flow and any(ch in s for ch in ",{}[]:")))
    if not risky:
        return s
    for q in "\"'":
        if q not in s:
            return q + s + q
    raise CasesError("a value with both quote kinds cannot be written: %r" % s[:40])


def _key(k):
    if not _KEY.match(str(k)):
        raise CasesError("extra keys must be plain names: %r" % k)
    return str(k)


def render(key, value):
    if key == "occurrences" and value:
        items = ", ".join
        return ["occurrences:"] + ["  - { %s }" % items("%s: %s" % (k, scalar(o[k], True))
                                                       for k in ("due_at", "status", "done_at", "note")
                                                       if o.get(k) is not None) for o in value]
    return ["%s: %s" % (key, scalar(value))]


def _blocks(fm):
    out = []
    for line in fm:
        top = line[:1] not in ("", " ", "\t", "#") and ":" in line
        if top or not out:
            out.append([line.split(":", 1)[0].strip() if top else None, [line]])
        else:
            out[-1][1].append(line)
    return out


def set_fields(text, updates):
    """`updates`: key -> value, or DELETE to drop the key. A file without
    frontmatter gets one."""
    fm, body = split(text)
    if not fm and not text.startswith("---"):
        body = "\n" + text if text else ""
    blocks = _blocks(fm)
    done = set()
    for b in blocks:
        if b[0] in updates:
            v = updates[b[0]]
            b[1] = [] if v is DELETE else render(b[0], v)
            done.add(b[0])
    for k, v in updates.items():
        if k not in done and v is not DELETE:
            blocks.append([k, render(k, v)])
    lines = [line for b in blocks for line in b[1]]
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n" + body.lstrip("\r")


def new_file(fields, body=""):
    lines = [line for k, v in fields.items() if v is not DELETE for line in render(k, v)]
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n" + ("\n" + body if body else "")
