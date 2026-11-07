"""`propose-scan`: the raw material for the post-install proposal, condensed.

One run walks every note under the brain (not <brain>/cases/) and prints, per
note, 1-3 lines: path | title | the dated / recurring frontmatter | the few
sentences that carry a date, a rhythm or a deadline. The agent still decides
what is a case (PROPOSE.md); this only replaces `cat`-ing every note. A note
with no signal is still listed by title, so nothing is invisible.
"""
import json
import re
from pathlib import Path

from common import CasesError

MONTH = (r"jan|feb|m[aá]rc|[aá]pr|m[aá]j|j[uú]n|j[uú]l|aug|szep|okt|nov|dec|"
         r"january|february|march|april|may|june|july|august|september|october|november|december")
DAY = r"hétfő|kedd|szerda|csütörtök|péntek|szombat|vasárnap|monday|tuesday|wednesday|thursday|friday"
PATTERNS = (
    (3, r"\b\d{4}[-./]\s?\d{1,2}[-./]\s?\d{1,2}\b"),
    (3, r"\b\d{1,2}\.?\s?(?:%s)[a-zá-ű]*\b|\b(?:%s)[a-zá-ű]*\.?\s\d{1,2}\b" % (MONTH, MONTH)),
    (3, r"\b\d{1,2}\s?[-.]?\s?(?:[aáeé]n|[aáeé]ig|ig|[aáeé]re|ra|re)\b"),
    (3, r"határid[őo]|deadline|\bdue\b|esed[ée]kes|lejár|[ée]rv[ée]nyes|\bhéten|\bhétig"),
    (2, r"minden\s+\S+|havonta|hetente|[ée]vente|negyed[ée]v|heti\b|havi\b|monthly|weekly|yearly|quarterly|\bevery\b"),
    (2, r"\b(?:%s)\w*" % DAY),
    (1, r"\[ \]|\bkell\b|\bmust\b|\bneed to\b|\bszólni\b"),
)
DATE_KEYS = re.compile(r"due|deadline|date|start|end|expire|renew|review|next|recurr|repeat|rhythm|schedule|status", re.I)
DATEISH = re.compile(r"\d{4}-\d{2}-\d{2}|monthly|weekly|yearly|quarterly|minden|havi|heti")


def split_note(text):
    """(frontmatter lines, body text) — a note without frontmatter has none."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            return text[4:end].splitlines(), text[end + 4:]
    return [], text


def title_of(fm, body, path):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    for line in fm:
        if re.match(r"(title|name):", line):
            return line.split(":", 1)[1].strip().strip("\"'")
    return path.stem.replace("-", " ")


def fm_signal(fm):
    out = []
    for line in fm:
        k, sep, v = line.partition(":")
        if sep and v.strip() and k.strip() == k and (DATE_KEYS.search(k) or DATEISH.search(v)):
            out.append("%s=%s" % (k.strip(), v.strip()[:40]))
    return ", ".join(out[:6])


def sentences(body):
    for para in re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+\.)\s)", body):
        flat = re.sub(r"\s+", " ", para.replace("**", "")).strip(" -*")
        if not flat or flat.startswith("#") or re.match(r"\[[xX]\]", flat):
            continue
        yield from (s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÁ-Ű0-9])", flat) if s.strip())


def score(s):
    return sum(w for w, p in PATTERNS if re.search(p, s, re.I))


def clip(s, width):
    """Fit `s` in `width`, keeping the first date / rhythm hit in view."""
    if len(s) <= width:
        return s
    hit = next((m.start() for w, pat in PATTERNS if w >= 2 for m in [re.search(pat, s, re.I)] if m), 0)
    start = max(0, min(hit - 40, len(s) - width + 1)) if hit > width - 40 else 0
    return ("…" if start else "") + s[start:start + width - 1] + ("…" if start + width - 1 < len(s) else "")


def scan_note(path, rel, limit, width):
    fm, body = split_note(path.read_text(encoding="utf-8", errors="replace"))
    head = "%s | %s" % (rel, title_of(fm, body, path))
    sig = fm_signal(fm)
    if sig:
        head += " | " + sig
    ranked = [(score(s), n, s) for n, s in enumerate(sentences(body))]
    best = sorted((r for r in ranked if r[0] >= 2), key=lambda r: (-r[0], r[1]))[:limit]
    lines = [clip(s, width) for _, _, s in sorted(best, key=lambda r: r[1])]
    return {"note": rel, "title": head.split(" | ")[1], "frontmatter": sig, "lines": lines}, head, lines


def run(args, root, brain):
    base = Path(root) / brain
    if not base.is_dir():
        raise CasesError("no brain folder %s/" % brain)
    skip = base / "cases"
    notes = sorted(p for p in base.rglob("*.md") if skip not in p.parents and p.name != "_meta.md")
    limit = None if args.full else args.lines
    rows, text = [], []
    for p in notes:
        row, head, lines = scan_note(p, p.relative_to(root).as_posix(), limit or 99, 10 ** 6 if args.full else 150)
        rows.append(row)
        text.append(head)
        text += ["  " + s for s in lines]
    if args.json:
        return json.dumps(rows, ensure_ascii=False, indent=1), 0
    quiet = sum(1 for r in rows if not r["lines"] and not r["frontmatter"])
    tail = ("%d notes, %d without a date or rhythm signal (title only) — open one only if its title hints at a deadline. "
            "Next: write .mentat/cases-proposal.json, then `proposal check`." % (len(rows), quiet))
    return "\n".join(text + [tail]), 0
