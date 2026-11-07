"""The recipients of a final step, for mentat_final.py preview: listed one by one, exclusions enforced.

recipients(doc) -> [address]: the payload's to / cc / bcc / recipients (a list, or a comma or
semicolon separated text). excluded(found, exclude) -> the ones that must not get it (case and
spaces ignored). lines(found) -> "Recipients (N):" and one per line, so the USER sees every one.
"""
import re

KEYS = ("to", "cc", "bcc", "recipients", "címzett", "címzettek")


def _split(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[,;]", str(v or "")) if x.strip()]


def recipients(doc):
    if not isinstance(doc, dict):
        return []
    return [r for k in KEYS if k in doc for r in _split(doc[k])]


def excluded(found, exclude):
    norm = lambda s: re.sub(r"\s+", "", s).casefold()  # noqa: E731
    out = {norm(x) for x in _split(exclude)}
    return [r for r in found if norm(r) in out or any(o and o in norm(r) for o in out if "@" in o)]


def lines(found):
    return ["Recipients (%d):" % len(found)] + ["  - %s" % r for r in found] if found else []
