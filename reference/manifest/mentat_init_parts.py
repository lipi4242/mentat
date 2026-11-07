"""Which Mentat parts are in this folder, from the files alone (no LLM, nothing written).

    python3 .mentat/bin/mentat_init.py --parts [--repo .]

parts(root) -> [(part, ok, how to get it)]: brain (AGENTS.md with the product blocks +
mentat.json components.brain), guard (the hook in .claude/settings.json and its code), engine
(components.engine and its package on disk). lines(root) prints one PARTS line, one MISSING line
per absent part, and the rule: say it plainly and offer it; a hand-built replacement only on
the USER's yes to that replacement. mentat_init.py prints it after every HIBA as well.
"""
import argparse
import json
import pathlib

INSTALL = "INSTALL.md step 2 (reference/initialization.md) again, with the USER's yes"
ENGINE = ("the same mentat_init.py command again, with --engine --tz <the USER's timezone> "
          "(it installs the engine pinned to this release; nothing else changes)")
RULE = {"hu": "SZABÁLY: a hiányzó részt mondd ki egyszerű szavakkal, és ajánld fel a telepítését; helyette "
              "saját megoldást (szkript, időzítő, ütemező) csak a FELHASZNÁLÓ arra a pótlásra mondott "
              "igenjével építs — a „csináld, ahogy jónak látod” nem ilyen igen.",
        "en": "RULE: say a missing part plainly and offer to install it; build your own replacement "
              "(script, timer, scheduler) only on the USER's yes to that replacement — \"do it however "
              "is best\" is not that yes."}


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def parts(root):
    root = pathlib.Path(root)
    comp = _json(root / "mentat.json").get("components") or {}
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    brain = bool(comp.get("brain")) and "mentat:managed:start reference-manual -->" in text
    settings = (root / ".claude" / "settings.json")
    hooked = settings.is_file() and "szerep_guard.py" in settings.read_text(encoding="utf-8")
    guard = hooked and (root / ".mentat" / "bin" / "bekotes" / "szerep_guard.py").is_file()
    eng = comp.get("engine") if isinstance(comp.get("engine"), dict) else None
    eng_path = root / (eng or {}).get("path", "anytime_engine")
    engine = bool(eng) and (eng_path / "tick.py").is_file()
    return [("brain", brain, INSTALL),
            ("guard", guard, INSTALL if not brain else "python3 .mentat/bin/mentat_scaffold.py --lang <hu|en>"),
            ("engine", engine, ENGINE if not eng else "its files are gone: " + ENGINE)]


def lines(root, lang="en"):
    got = parts(root)
    out = ["PARTS " + " · ".join("%s %s" % (p, "ok" if ok else "MISSING") for p, ok, _ in got)]
    out += ["MISSING %s — to install it: %s" % (p, how) for p, ok, how in got if not ok]
    if any(not ok for _, ok, _ in got):
        out.append(RULE.get(lang, RULE["en"]))
    return out


def cli(argv):
    """--parts [--repo .] [--lang en]: print the lines; True when it was asked for."""
    pre = argparse.ArgumentParser(add_help=False)
    for flag, default in (("--repo", "."), ("--lang", "en")):
        pre.add_argument(flag, default=default)
    pre.add_argument("--parts", action="store_true")
    a = pre.parse_known_args(argv)[0]
    if a.parts:
        print("\n".join(lines(a.repo, a.lang)))
    return a.parts
