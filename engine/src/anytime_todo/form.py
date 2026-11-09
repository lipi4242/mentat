"""The developer's AC form (A–F): rendered from the live item, parsed back for submit.

`item show REF --form` prints it with the item's live AC ids and texts; the
developer fills it; `item submit REF --form f.md` sends exactly those rows.
Sections: Meta (summary, head_sha, pr links) · A one result per AC (verdict +
evidence) · B tests · C review · D gates · E verdict (derived, never typed) ·
F attachments. B, C, D and F travel as the report body, headings included.
The headings may be translated; the parser keys on "Meta" and on "A)".."F)".
"""
from __future__ import annotations

import re
from typing import Any

VERDICTS = ("met", "not_met", "na")
MARK = re.compile(r"<!-- mentat:ac-form item=(\S+) round=(\d+) -->")
HEAD = {
    "en": ["Meta", "A) Acceptance criteria", "B) Tests", "C) Review", "D) Gates", "E) Verdict",
           "F) Attachments"],
    "hu": ["Meta", "A) Elfogadási feltételek", "B) Tesztek", "C) Review", "D) Kapuk", "E) Verdikt",
           "F) Csatolmányok"],
}
META_HINT = {
    "en": "head_sha: the commit, 7-40 hex · pr: a full http(s) URL, one per line, or leave it empty",
    "hu": "head_sha: a commit, 7-40 hexa jegy · pr: teljes http(s) URL, soronként egy, vagy hagyd üresen",
}
HINT = {
    "en": ["which test covers which AC, the command and its result; does the test really assert the AC?",
           "the load-bearing claims, challenged; each finding and how it was resolved",
           "the gates of the track, green; a UI change needs screenshots",
           "derived on submit: yes only if every AC is met or na", "what is attached (PR, logs, screenshots)"],
    "hu": ["melyik teszt melyik AC-t fedi, a parancs és az eredmény; tényleg az AC-t állítja-e a teszt?",
           "a teherhordó állítások, megtámadva; minden lelet és a feloldása",
           "a sáv kapui, zölden; UI-változásnál képernyőkép kell",
           "beküldéskor számolódik: csak akkor igen, ha minden AC met vagy na",
           "mi van csatolva (PR, napló, képernyőkép)"],
}


class FormError(ValueError):
    """The form cannot be submitted as it is; nothing was sent."""


def next_round(item: dict[str, Any]) -> int:
    return max((int(r.get("round") or 0) for r in item.get("reports") or []), default=0) + 1


def render(item: dict[str, Any], lang: str = "en") -> str:
    h, hint = HEAD.get(lang, HEAD["en"]), HINT.get(lang, HINT["en"])
    out = [f"# {item.get('key') or item['id']}: {item.get('title', '')}",
           f"<!-- mentat:ac-form item={item['id']} round={next_round(item)} -->", "",
           f"## {h[0]}", f"<!-- {META_HINT.get(lang, META_HINT['en'])} -->",
           "- summary: ", "- head_sha: ", "- pr: ", "", f"## {h[1]}"]
    for ac in item.get("acs") or []:
        out += ["", f"### AC {ac['id']}", "> " + str(ac["text"]).replace("\n", "\n> "),
                "- verdict: " + " | ".join(VERDICTS), "- evidence: "]
    for title, text in zip(h[2:], hint):
        out += ["", f"## {title}", f"<!-- {text} -->"]
    return "\n".join(out).rstrip() + "\n"


FENCE = re.compile(r"^\s*(```|~~~)")
STRUCT = re.compile(r"^## (?:(Meta)\b|([A-F])\))", re.I)


def _outside(lines: list[str]) -> list[bool]:
    """For each line: is it outside a fenced code block (``` or ~~~)?"""
    out, fence = [], None
    for line in lines:
        m = FENCE.match(line)
        out.append(fence is None and not m)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
    return out


def _sections(text: str) -> dict[str, str]:
    """The structural sections. A `## ` line counts only outside code fences and only
    for Meta / A)..F); any other line belongs to the section it is in. Text before
    Meta (beyond the title and the marker), a doubled section and typed text in E
    are refused: nothing the developer wrote is dropped silently."""
    lines = text.splitlines()
    out: dict[str, list[str]] = {}
    cur: list[str] | None = None
    for line, free in zip(lines, _outside(lines)):
        m = STRUCT.match(line) if free else None
        if m:
            k = "Meta" if m.group(1) else m.group(2).upper()
            if k in out:
                raise FormError(f"the form has two {k} sections: keep one")
            cur = out[k] = [line.strip()]
        elif cur is not None:
            cur.append(line)
        elif line.strip() and not line.startswith("# ") and not MARK.search(line):
            raise FormError(f"text before the Meta section is not part of the form: {line.strip()[:60]!r}")
    if re.sub(r"<!--.*?-->", "", "\n".join(out.get("E", [])[1:]), flags=re.S).strip():
        raise FormError("E) is derived on submit: leave it empty")
    return {k: "\n".join(v) for k, v in out.items()}


def _results(block: str) -> list[dict[str, str]]:
    """One row per `### AC <id>` (outside fences). The `>` quote before `- evidence:` is
    the AC text; everything after `- evidence:` (quotes and code included) is evidence."""
    rows: list[dict[str, Any]] = []
    lines = block.splitlines()
    for line, free in zip(lines, _outside(lines)):
        s = line.strip()
        if free and s.startswith("### AC "):
            rows.append({"ac_id": s[len("### AC "):].strip(), "verdict": "", "quote": [],
                         "evidence": [], "in_ev": False})
        elif not rows:
            continue
        elif (r := rows[-1])["in_ev"]:
            if free and s.startswith("- verdict:"):
                r["verdict"], r["in_ev"] = s[len("- verdict:"):].strip(), False
            else:
                r["evidence"].append(line.rstrip())
        elif s.startswith(">"):
            r["quote"].append(s[1:].strip())
        elif s.startswith("- verdict:"):
            r["verdict"] = s[len("- verdict:"):].strip()
        elif s.startswith("- evidence:"):
            r["evidence"], r["in_ev"] = [s[len("- evidence:"):].strip()], True
        elif s:
            raise FormError(f"AC {r['ac_id']}: unexpected line before evidence: {s[:60]!r}")
    return [{"ac_id": r["ac_id"], "verdict": r["verdict"], "quoted": " ".join(r["quote"]),
             "evidence": "\n".join(r["evidence"]).strip()} for r in rows]


def parse(text: str) -> dict[str, Any]:
    m = MARK.search(text)
    if not m:
        raise FormError("not an AC form (the mentat:ac-form line is missing): "
                        "get one with `item show REF --form`")
    sec = _sections(text)
    meta: dict[str, list[str]] = {}
    for line in sec.get("Meta", "").splitlines()[1:]:
        if not line.strip() or line.strip().startswith("<!--"):
            continue
        k, sep, v = line.strip().removeprefix("- ").partition(":")
        if not sep or k.strip() not in ("summary", "head_sha", "pr"):
            raise FormError(f"Meta: only summary, head_sha and pr lines belong here: {line.strip()[:60]!r}")
        if v.strip():
            meta.setdefault(k.strip(), []).append(v.strip())
    body = "\n\n".join(re.sub(r"<!--.*?-->", "", sec[k], flags=re.S).strip()
                       for k in "BCDF" if k in sec)
    return {"item": m.group(1), "round": int(m.group(2)), "results": _results(sec.get("A", "")),
            "summary": " ".join(meta.get("summary", [])),
            "head_sha": ((meta.get("head_sha") or [None])[0] or "").lower() or None,
            "prs": meta.get("pr", []), "body": body or None}
