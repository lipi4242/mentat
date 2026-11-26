"""The product blocks of AGENTS.md at an upgrade: refresh the ones that are there, add the missing.

Text between `<!-- mentat:managed:start ID -->` and `<!-- mentat:managed:end ID -->` belongs to
the product (the file itself says so); everything outside the markers is the USER's and is
never touched. refreshed(text, lang, base) -> (new text, [changed ids]) replaces each complete
block with this release's template; a block with a missing or doubled marker is left alone and
reported, the missing blocks are appended by mentat_scaffold (append_blocks).
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent


def template_blocks(lang, base):
    tpl = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
    base = base if base.endswith("/") else base + "/"
    out = {}
    for m in re.finditer(r"<!-- mentat:managed:start ([a-z-]+) -->.*?<!-- mentat:managed:end \1 -->", tpl, re.S):
        out[m.group(1)] = m.group(0).replace("{BASE}", base).replace("{LANG}", lang)
    return out


def refreshed(text, lang, base):
    """(text, changed, broken): broken = ids whose markers are not exactly one start + one end."""
    changed, broken = [], []
    for bid, block in template_blocks(lang, base).items():
        start, end = "<!-- mentat:managed:start %s -->" % bid, "<!-- mentat:managed:end %s -->" % bid
        n_start, n_end = text.count(start), text.count(end)
        if n_start == n_end == 0:
            continue
        if n_start != 1 or n_end != 1 or text.index(start) > text.index(end):
            broken.append(bid)
            continue
        a, b = text.index(start), text.index(end) + len(end)
        if text[a:b] != block:
            text = text[:a] + block + text[b:]
            changed.append(bid)
    return text, changed, broken
