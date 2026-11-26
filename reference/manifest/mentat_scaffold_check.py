#!/usr/bin/env python3
"""Verify the brain skeleton without writing anything: exit 0 = complete (append_blocks writes).

Shared by mentat_scaffold.py (--check) and usable on its own:
    python3 mentat_scaffold_check.py --lang hu|en [--repo .]
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
IGNORES = [".env", ".env.*", ".mentat/"]
IDS = ["reference-manual", "layers", "brain-dumps", "entities", "files",
       "frameworks", "claims", "large-work"]
NEWER_IDS = ["intake"]  # added after 0.2: missing in an older brain = WARN, not a failure


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None


def layout(lang):
    return json.loads((HERE / "scaffold-meta.json").read_text(encoding="utf-8"))[lang]


def upgrade_hint(root, lang, block):
    tpl = HERE / ("scaffold-agents.%s.md" % lang)
    try:
        tpl = tpl.relative_to(root.resolve())
    except ValueError:
        pass
    return ("WARN missing managed block %s (newer product rule) — fix: { echo; sed -n "
            "'/managed:start %s -->/,/managed:end %s -->/p' '%s'; } >> AGENTS.md"
            % (block, block, block, tpl))


def missing_blocks(text, lang, base):
    """[(id, block)]: the product blocks AGENTS.md lacks entirely, from the template (a half-present
    block is not here: it fails the check). Takeover: the file's own text is kept as it is."""
    tpl = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
    found = re.search(r"^`(https://raw\.githubusercontent\.com/lipi4242/mentat/v[0-9.]+/)`", text, re.M)
    base = base or (found.group(1) if found else "")
    base = base if not base or base.endswith("/") else base + "/"
    out = []
    for i in IDS + NEWER_IDS:
        if "mentat:managed:start %s -->" % i in text or "mentat:managed:end %s -->" % i in text:
            continue
        block = re.search(r"<!-- mentat:managed:start %s -->.*?<!-- mentat:managed:end %s -->\n" % (i, i),
                          tpl, re.S).group(0)
        if base or "{BASE}" not in block:
            out.append((i, block.replace("{BASE}", base).replace("{LANG}", lang)))
    return out


def append_blocks(path, lang, base):
    """The one writer here (mentat_scaffold.py calls it): the missing blocks at the end of AGENTS.md."""
    add = missing_blocks(path.read_text(encoding="utf-8"), lang, base)
    if add:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write("".join("\n" + block for _, block in add))
    return "exists  AGENTS.md (left as it is%s)" % ("; added at the end: " + ", ".join(i for i, _ in add)
                                                   if add else "")


def self_image(root, lang, text, warnings):
    """The self-image block: missing in an older brain = WARN; out of order or stale = a problem."""
    import mentat_self_image as si
    try:
        bad = si.problems(text, si.block(si.facts(root, lang)))
    except si.TooBig as e:
        return ["TOO BIG %s" % e]
    if any(b.startswith("MISSING") for b in bad):
        warnings.append("WARN missing self-image block (newer product rule) - fix: python3 "
                        ".mentat/bin/mentat_self_image.py")
    return [b for b in bad if not b.startswith("MISSING")]


def check(root, lang):
    problems, warnings = [], []
    agents = root / "AGENTS.md"
    if not agents.exists():
        problems.append("MISSING AGENTS.md")
    else:
        text = agents.read_text(encoding="utf-8")
        problems += ["OPEN placeholder %s" % p for p in re.findall(r"<[^<>\n]*TBD>", text)]
        problems += ["MISSING managed block %s (mentat_scaffold.py --base <manual URL> adds it; never rewrite "
                     "AGENTS.md)" % i for i in IDS
                     if text.count("mentat:managed:start %s -->" % i) != 1
                     or text.count("mentat:managed:end %s -->" % i) != 1]
        if len(text.splitlines()) > 200:
            problems.append("TOO LONG AGENTS.md is over 200 lines: shorten the USER's own sections with "
                            "their yes, never a managed block")
        warnings += [upgrade_hint(root, lang, i) for i in NEWER_IDS
                     if "mentat:managed:start %s -->" % i not in text]
        problems += self_image(root, lang, text, warnings)
    import mentat_skills
    warnings += ["WARN missing %s (newer product rule) - fix: python3 .mentat/bin/mentat_skills.py --lang %s"
                 % (m, lang) for m in mentat_skills.missing(root)]
    claude = root / "CLAUDE.md"
    if not claude.exists() or "@AGENTS.md" not in claude.read_text(encoding="utf-8").splitlines():
        problems.append("MISSING @AGENTS.md line in CLAUDE.md")
    problems += ["MISSING %s/_meta.md" % d for d in layout(lang)["dirs"]
                 if not (root / d / "_meta.md").exists()]
    ignore = root / ".gitignore"
    have = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    problems += ["MISSING %s in .gitignore" % i for i in IGNORES if i not in have]
    try:
        brain = json.loads((root / "mentat.json").read_text(encoding="utf-8"))["components"]["brain"]
    except (OSError, ValueError, KeyError, TypeError):
        brain = None
    if not brain:
        problems.append("MISSING mentat.json with components.brain (run with --name)")
    r = git(root, "rev-parse", "HEAD")
    if r is None or r.returncode != 0:
        problems.append("MISSING first commit (run with --commit)")
    print("\n".join(problems + warnings) if problems else
          "\n".join(warnings + ["OK brain skeleton complete"]))
    return 1 if problems else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_scaffold_check.py")
    p.add_argument("--lang", required=True, choices=["hu", "en"])
    p.add_argument("--repo", default=".")
    a = p.parse_args(argv)
    return check(pathlib.Path(a.repo), a.lang)


if __name__ == "__main__":
    sys.exit(main())
