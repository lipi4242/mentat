"""`szerep-onkep`: the active role self-image (<root>/szerep-onkep.md) and the upgrade decision.

The default is the `## Szerep önkép` / `## Role self-image` section of the shipped role template;
the active copy is one user-owned block per role in <root>/szerep-onkep.md. `alap` is the sha256 of
the default the block started from (`alap=custom` for a role with no shipped template). `decide`
is pure: it never reads or writes files.
"""
import difflib
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
FILE = "szerep-onkep.md"
CUSTOM = "custom"
HEAD = {"hu": "## Szerep önkép", "en": "## Role self-image"}
BEIR, SEMMI, CSERE, MARAD, FELAJANL = "beir", "semmi", "csere", "marad", "felajanl"
OPEN = "<!-- mentat:user-owned szerep-onkep szerep=%s alap=%s verzio=%s -->"
CLOSE = "<!-- /mentat:user-owned -->"
BLOCK = re.compile(r"<!-- mentat:user-owned szerep-onkep szerep=(\S+) alap=(\S+) verzio=(\S+) -->\n"
                   r"(.*?)\n?<!-- /mentat:user-owned -->", re.S)
INTRO = {
    "hu": "# Szerep önkép\n\nSzerepenként egy blokk: ez az önképed, ezt kövesd. A gazda kérésére a blokk "
          "szövegét írod át, az `alap` és a `verzio` mezőt nem, és a változást döntésként rögzíted "
          "(`python3 .mentat/bin/mentat_brain.py new decision \"<cím>\"`). Frissítés a módosított "
          "blokkot soha nem írja felül.\n",
    "en": "# Role self-image\n\nOne block per role: this is your self-image, follow it. When the owner "
          "asks, you rewrite the block's text, never the `alap` and `verzio` fields, and record the change "
          "as a decision (`python3 .mentat/bin/mentat_brain.py new decision \"<title>\"`). An upgrade "
          "never overwrites a changed block.\n",
}
POINTER = {
    "hu": "Az aktív önképed az `agy/szerep-onkep.md` `szerep=%s` blokkjában van; azt kövesd. A gazda "
          "kérésére ott írod át (az `alap` mezőhöz nem nyúlsz), és döntésként rögzíted.",
    "en": "Your active self-image is the `szerep=%s` block of `agy/szerep-onkep.md`; follow it. When the "
          "owner asks, you rewrite it there (never the `alap` field) and record it as a decision.",
}


def norm(text):
    """Trailing spaces off every line, `\\n` line endings, no blank lines around."""
    return "\n".join(l.rstrip() for l in text.replace("\r\n", "\n").split("\n")).strip("\n")


def digest(text):
    return "sha256:" + hashlib.sha256(norm(text).encode("utf-8")).hexdigest()


def section(text, lang):
    """The self-image section of a role file (without its heading), or None."""
    head = HEAD[lang]
    m = re.search(r"^%s[ \t]*\n(.*?)(?=^## |\Z)" % re.escape(head), text or "", re.S | re.M)
    return norm(m.group(1)) if m else None


def decide(block, alap, default):
    """What an upgrade does with one role's block. block: the active text or None; alap: the
    block's `alap` field; default: the new shipped default or None (no template)."""
    if block is None:
        return BEIR
    if alap == CUSTOM or default is None:
        return MARAD
    now, new = digest(block), digest(default)
    if now == new:
        return SEMMI
    if now == alap:
        return SEMMI if new == alap else CSERE
    return MARAD if new == alap else FELAJANL


def diff(block, default, name):
    return "".join(difflib.unified_diff((norm(block) + "\n").splitlines(True),
                                        (norm(default) + "\n").splitlines(True),
                                        "%s (aktív)" % name, "%s (új alapérték)" % name))


def parse(text):
    """{role: {"alap", "verzio", "text"}} from the content of szerep-onkep.md."""
    return {m.group(1): {"alap": m.group(2), "verzio": m.group(3), "text": norm(m.group(4))}
            for m in BLOCK.finditer(text or "")}


def render(name, text, alap, ver):
    return "%s\n%s\n%s\n" % (OPEN % (name, alap, ver), norm(text), CLOSE)


def version():
    try:
        return str(json.loads((HERE.parent / "release.json").read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def template(name, lang):
    p = HERE / "szerepek" / ("%s.%s.md" % (name, lang))
    return section(p.read_text(encoding="utf-8"), lang) if p.is_file() else None


def pointer(tpl, name, lang):
    """The role file as installed: its self-image section points at the active block."""
    head = HEAD[lang]
    return re.sub(r"^%s[ \t]*\n.*?(?=^## |\Z)" % re.escape(head),
                  lambda m: "%s\n\n%s\n\n" % (head, POINTER[lang] % name), tpl, count=1, flags=re.S | re.M)


def write(repo, root, names, lang):
    """Add a block for every role in `names` that has none; never touch an existing block."""
    repo = pathlib.Path(repo)
    path = repo / root / FILE
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    have, add = parse(old), []
    for n in (x for x in names if x not in have):
        default, own = template(n, lang), repo / root / "szerepek" / (n + ".md")
        text = default if default is not None else (
            section(own.read_text(encoding="utf-8"), lang) if own.is_file() else None)
        if text:  # a custom role (no shipped template) starts from its own file and is never replaced
            add.append(render(n, text, digest(text) if default is not None else CUSTOM, version()))
    if add:
        path.parent.mkdir(parents=True, exist_ok=True)
        base = old or INTRO[lang]
        path.write_bytes((base.rstrip("\n") + "\n\n" + "\n".join(add)).encode("utf-8"))
    return bool(add)


def plan(repo, root, names, lang):
    """[(role, action, diff or None)] for an upgrade: what each role's block should get."""
    path = pathlib.Path(repo) / root / FILE
    have = parse(path.read_text(encoding="utf-8") if path.is_file() else "")
    out = []
    for n in names:
        b, default = have.get(n), template(n, lang)
        act = decide(b and b["text"], b and b["alap"], default)
        out.append((n, act, diff(b["text"], default, n) if act == FELAJANL else None))
    return out
