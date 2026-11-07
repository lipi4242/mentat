"""Lexical search over the capability index: the user's words against the curated intents
(HU + EN), the ids, commands and descriptions. Accents are folded and Hungarian suffixes
are met by prefix matching ("meghívót" ~ "meghívó", "táblát" ~ "tábla"). No embeddings:
those come only after a measured miss.
"""
import re
import unicodedata

STOP = set("""a az egy es is hogy ezt azt ez ezek nekik neki nekem nekunk en te mi ki be meg el le fel
nem ne de van lesz legyen kell mar ami aki amit the an to for of me them it this that my and or in
on so can is who has not be with at by from please you your we us our what which do does""".split())
THRESHOLD = 2.0
W_INTENT, W_NAME, W_TEXT, W_OWN_TEXT = 3.0, 2.0, 1.0, 2.0


def tokens(text):
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= 3 and t not in STOP]


def _match(q, c):
    if q == c:
        return 1.0
    short, long_ = sorted((q, c), key=len)
    if len(short) >= 4 and long_.startswith(short):
        return 0.8
    n = 0
    while n < len(short) and short[n] == long_[n]:
        n += 1
    return 0.6 if n >= 5 and n >= 0.6 * len(short) else 0.0


def _bags(e):
    intents = [p for lang in ("hu", "en") for p in (e.get("intents") or {}).get(lang, [])]
    names = tokens(e["id"].replace(".", " ").replace("_", " ")) + tokens(e.get("entry") or "")[:12]
    summary = e.get("summary") or {}
    text = tokens(" ".join(summary.values()) if isinstance(summary, dict) else summary)
    bags = [(tokens(" ".join(intents)), W_INTENT), (names, W_NAME), (text, W_TEXT)]
    if e.get("own_text"):
        bags.append((tokens(e["own_text"]), W_OWN_TEXT))
    return bags, [tokens(p) for p in intents if len(tokens(p)) >= 2]


def score(qtok, e):
    bags, phrases = _bags(e)
    total = 0.0
    for q in qtok:
        total += max([_match(q, c) * w for toks, w in bags for c in toks] or [0.0])
    for ph in phrases:
        if all(any(_match(q, t) for q in qtok) for t in ph):
            total += 2.0
    return round(total, 2)


def search(entries, query, limit=5):
    """(hits, near): hits pass the threshold, near are the weaker matches."""
    qtok = tokens(query)
    scored = [(score(qtok, e), e) for e in entries]
    order = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]["provenance"] == "suite"))
    hits = [s for s in order if s[0] >= THRESHOLD][:limit]
    near = [s for s in order if s[0] < THRESHOLD][:3]
    return hits, near


def categories(entries):
    seen = {}
    for e in entries:
        seen[e["category"]] = seen.get(e["category"], 0) + 1
    return sorted(seen.items())
