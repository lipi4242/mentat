"""The words mentat_dates.py understands (English and Hungarian), as concepts, not phrases.

Tokens are lower-case and accent-free ("jövő héten" -> jovo, heten). Hungarian inflects, so
its words match by stem; English by the whole word. A word that is not here is simply not
understood: the tool then says so instead of guessing.
"""
import re
import unicodedata

EXACT = {
    "next": {"next", "coming", "upcoming", "following"}, "this": {"this", "current"},
    "last": {"last", "previous", "past"}, "today": {"today"}, "tomorrow": {"tomorrow"},
    "yesterday": {"yesterday"}, "in": {"in"}, "within": {"within"}, "by": {"by", "until", "till", "before"},
    "end": {"end"}, "on": {"on"}, "after": {"after"}, "from": {"from"}, "now": {"now"},
    "day": {"day", "days"}, "week": {"week", "weeks"}, "weekend": {"weekend"}, "month": {"month", "months"},
    "fortnight": {"fortnight"},
    # Hungarian words that do not inflect in these phrases
    "hu_this": {"ez", "ezen", "e", "jelen", "mostani", "folyo"}, "hu_today": {"ma"},
    "hu_in": {"mulva"}, "hu_within": {"belul"},
}
STEMS = [  # (stem, concept) — the first match wins, so the longer, more specific stem comes first
    ("holnaputan", "dayafter"), ("holnap", "tomorrow"), ("tegnap", "yesterday"), ("hetvege", "weekend"),
    ("hetfo", "wd0"), ("kedd", "wd1"), ("szerd", "wd2"), ("csutortok", "wd3"), ("pentek", "wd4"),
    ("szombat", "wd5"), ("vasarnap", "wd6"), ("jovo", "next"), ("kovetkezo", "next"),
    ("rakovetkezo", "next"), ("mult", "last"), ("elozo", "last"), ("honap", "month"), ("het", "week"),
    ("nap", "day"), ("vege", "end"),
]
WEEKDAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10, "fourteen": 14, "egy": 1, "ket": 2, "ketto": 2, "harom": 3,
           "negy": 4, "ot": 5, "hat": 6, "het": 7, "nyolc": 8, "kilenc": 9, "tiz": 10, "tizennegy": 14}
UNITS = {"day", "week", "month", "fortnight"}
STOP = {"of", "the", "at", "during", "for", "due", "is", "it", "around", "esedekes", "az", "legkesobb",
        "kb", "korul", "folyaman", "soran", "napjan"}
ARTICLE = {"a", "an"}  # "in a week" = one; the Hungarian article "a" is dropped
GLUED = ("jovo", "mult", "ez")  # "jövőhéten" is written as one word


def plain(text):
    s = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    out = []
    for t in re.findall(r"[a-z]+|\d{4}-\d\d-\d\d|\d+", s):
        g = next((p for p in GLUED if t.startswith(p) and len(t) > len(p) + 2 and t[len(p):].startswith("het")), None)
        out += [g, t[len(g):]] if g else [t]
    return out


def concept(tok, following=None):
    """One token -> (concept, value). `het` is seven before a unit ("hét nap"), else week."""
    if re.fullmatch(r"\d{4}-\d\d-\d\d", tok):
        return "date", tok
    if tok.isdigit():
        return "num", int(tok)
    if tok in NUMBERS and (tok != "het" or following in UNITS):
        return "num", NUMBERS[tok]
    if tok in WEEKDAYS_EN or tok.rstrip("s") in WEEKDAYS_EN:
        return "wd", WEEKDAYS_EN.index(tok.rstrip("s") if tok not in WEEKDAYS_EN else tok)
    for name, words in EXACT.items():
        if tok in words:
            return name.replace("hu_", ""), None
    if tok.endswith("ig") and len(tok) > 4:  # "péntekig", "hónap végéig": up to and including
        c = concept(tok[:-2])
        if c[0] not in ("?", "by"):
            return "by+" + c[0], c[1]
    for stem, name in STEMS:
        if tok.startswith(stem):
            return (("wd", int(name[2])) if name.startswith("wd") else (name, None))
    return "?", tok


def concepts(phrase):
    toks, out = plain(phrase), []
    for i, t in enumerate(toks):
        if t in STOP:
            continue
        if t in ARTICLE:
            if out and out[-1][0] in ("in", "within", "by"):
                out.append(("num", 1))
            continue
        nxt = concept(toks[i + 1])[0] if i + 1 < len(toks) else None
        c = concept(t, nxt)
        out += [("by", None), (c[0][3:], c[1])] if c[0].startswith("by+") else [c]
    return out
