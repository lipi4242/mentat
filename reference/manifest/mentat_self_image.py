#!/usr/bin/env python3
"""The `self-image` block, first in AGENTS.md: from mentat.json `roles` and <root>/szerep-onkep.md.

    python3 mentat_self_image.py [--repo .] [--lang hu|en] [--check]   # --check: exit 1 on drift

Name, main role, at most 3 more roles, the file; first line `<!-- self-image hash=… -->`; ≤600 bytes.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
ID = "self-image"
START, END = "<!-- mentat:managed:start %s -->" % ID, "<!-- mentat:managed:end %s -->" % ID
BLOCK = re.compile(r"%s.*?%s\n?" % (re.escape(START), re.escape(END)), re.S)
MAX_BYTES, MAX_MORE = 600, 3
ROOT = {"hu": "agy", "en": "brain"}
NAMES = {"hu": {"asszisztens": "asszisztens", "fejleszto": "fejlesztő", "consultant": "consultant",
                "backlog-manager": "product manager", "kiado": "kiadó ágens", "flottamenedzser": "flottamenedzser"},
         "en": {"asszisztens": "assistant", "fejleszto": "developer", "consultant": "consultant",
                "backlog-manager": "product manager", "kiado": "release agent", "flottamenedzser": "fleet manager"}}
TEXT = {"hu": {"pa": ("személyi asszisztens", "a gazda jobbkeze"),
               "me": "%s vagyok, %s: %s.", "me0": "%s vagyok, %s.",
               "more": "Ezen kívül a következő módokon gondolok magamra:", "line": "- %s: %s",
               "rest": "- és még %d: lásd az önkép-fájlt", "file": "Az önképem részletesen: @%s/szerep-onkep.md",
               "noname": "<ügynök neve TBD>", "as": "mint"},
        "en": {"pa": ("personal assistant", "the owner's right hand"),
               "me": "I am %s, %s: %s.", "me0": "I am %s, %s.",
               "more": "Besides that, I think of myself in these ways:", "line": "- %s: %s",
               "rest": "- and %d more: see the self-image file", "file": "My self-image in full: @%s/szerep-onkep.md",
               "noname": "<agent name TBD>", "as": "as"}}


class TooBig(ValueError):
    """Over MAX_BYTES: an error, never a cut."""


def _onkep():  # the role templates and the szerep-onkep.md parser, wherever the tools were put
    for d in (HERE, HERE / "bekotes", HERE.parent / "bekotes"):
        if (d / "szerep_onkep.py").is_file():
            sys.path.insert(0, str(d))
            try:  # optional: a brain without the onboarding tools renders without templates
                import szerep_onkep
                return szerep_onkep
            except ImportError:
                break
    return None


def phrase(text, lang):
    """What the role thinks of itself as: the `mint …` / `as …` part of the first sentence."""
    first = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    m = re.search(r"\b%s (.+?)(?::|[.!?]?$)" % TEXT[lang]["as"], first)
    return (m.group(1) if m else first).rstrip(".:;! ")


def _manifest(repo):
    try:
        got = json.loads((pathlib.Path(repo) / "mentat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def facts(repo, lang):
    repo, manifest = pathlib.Path(repo), _manifest(repo)
    t, so = TEXT[lang], _onkep()
    root = ((manifest.get("components") or {}).get("brain") or {}).get("root") or ROOT[lang]
    roles = manifest.get("roles") if isinstance(manifest.get("roles"), dict) else {}
    path = repo / root / "szerep-onkep.md"
    active = so.parse(path.read_text(encoding="utf-8")) if so and path.is_file() else {}

    def one(name):
        text = (active.get(name) or {}).get("text") or (so.template(name, lang) if so else None)
        return [NAMES[lang].get(name, name), phrase(text, lang) if text else ""]
    default = roles.get("default")
    more = [r for r in roles.get("installed") or [] if r != default]
    return {"name": (manifest.get("agent") or {}).get("name") or t["noname"], "lang": lang,
            "root": root if path.is_file() else None,  # no link to a file that is not there yet
            "main": one(default) if default else list(t["pa"]),
            "more": [one(r) for r in more[:MAX_MORE]], "rest": max(0, len(more) - MAX_MORE)}


def source_hash(f):
    return hashlib.sha256(json.dumps(f, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def block(f):
    t = TEXT[f["lang"]]
    main = t["me"] % (f["name"], *f["main"]) if f["main"][1] else t["me0"] % (f["name"], f["main"][0])
    lines = [START, "<!-- %s hash=%s -->" % (ID, source_hash(f)), main]
    if f["more"]:
        lines += [t["more"]] + [(t["line"] % tuple(x)) if x[1] else "- " + x[0] for x in f["more"]]
        lines += [t["rest"] % f["rest"]] if f["rest"] else []
    text = "\n".join(lines + ([t["file"] % f["root"]] if f["root"] else []) + [END]) + "\n"
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise TooBig("self-image: %d bájt > %d; rövidebb első önkép-mondat kell" % (len(text.encode()), MAX_BYTES))
    return text


def place(text, new):  # at the very top; an old block anywhere else is removed
    rest = BLOCK.sub("", text or "", count=1)
    return new + ("\n" + rest.lstrip("\n") if rest.strip() else "")


def problems(text, new):
    m = BLOCK.search(text or "")
    out = ["OPEN placeholder %s in self-image (mentat.json agent.name)" % x for x in re.findall(r"<[^<>\n]*TBD>", new)]
    return out + ["MISSING self-image block (mentat_self_image.py writes it)"] if not m else out + (
        [] if m.start() == 0 else ["ORDER self-image is not the first block of AGENTS.md"]) + (
        [] if m.group(0) == new else ["DRIFT self-image differs from mentat.json roles / szerep-onkep.md"])


def language(repo, lang):
    got = (_manifest(repo).get("agent") or {}).get("language")
    return lang or (got if got in TEXT else "hu")


def write(repo, lang=None):
    path = pathlib.Path(repo) / "AGENTS.md"
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    new = place(old, block(facts(repo, language(repo, lang))))
    if new != old:
        path.write_bytes(new.encode("utf-8"))
    return new != old


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_self_image.py")
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", choices=sorted(TEXT))
    p.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    try:
        new = block(facts(a.repo, language(a.repo, a.lang)))
    except TooBig as e:
        return print("error: %s" % e, file=sys.stderr) or 2
    path = pathlib.Path(a.repo) / "AGENTS.md"
    if a.check:
        bad = problems(path.read_text(encoding="utf-8") if path.is_file() else "", new)
        return print("\n".join(bad) if bad else "OK self-image") or (1 if bad else 0)
    print("written AGENTS.md self-image" if write(a.repo, a.lang) else "unchanged AGENTS.md self-image")
    return 0


if __name__ == "__main__":
    sys.exit(main())
