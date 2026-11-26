#!/usr/bin/env python3
"""The brain's skills as native Claude Code skills: .claude/skills/<name>/SKILL.md, the USER's language.

    python3 mentat_skills.py --lang hu|en [--repo .]   # install or update; mentat_scaffold.py calls it

The source is the release's skills/<name>/SKILL.<lang>.md: in an installed brain the copy the curl
step put in .mentat/bin/skills/ (checked against release.json by mentat_verify.py before anything
runs), in the dev tree the release's own skills/. No network. .mentat/state/skills.json records the
sha256 each skill was installed with: an untouched skill is replaced by a newer release, a skill the
USER edited is kept, and the run says where the new version is and how to see the difference.
Without .mentat/ (a bare scaffold) nothing is recorded, so a differing skill is always kept.
"""
import argparse
import hashlib
import json
import pathlib
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
SKILLS = ("develop", "subagent", "status", "backlog", "model", "bug-report")
STATE = pathlib.Path(".mentat") / "state" / "skills.json"
KEPT = ("a .claude/skills/%s/SKILL.md kézzel módosult, nem írtam felül; az új változat: %s "
        "(eltérés: diff -u .claude/skills/%s/SKILL.md %s)")


def source_dir():
    for d in (HERE / "skills", HERE.parent.parent / "skills"):
        if d.is_dir():
            return d
    return None


def rel(name):
    return pathlib.Path(".claude") / "skills" / name / "SKILL.md"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _state(root):
    try:
        got = json.loads((root / STATE).read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def install(root, lang, src=None):
    """Write the missing or untouched skills; keep an edited one and say so. Returns the log lines."""
    root, src = pathlib.Path(root), pathlib.Path(src) if src else source_dir()
    if src is None:
        return ["WARNING the skills are not next to the tools - rerun step 1, they are not installed"]
    state, log = _state(root), []
    for name in SKILLS:
        new_path = src / name / ("SKILL.%s.md" % lang)
        if not new_path.is_file():
            log.append("WARNING %s is missing - the %s skill is not installed" % (new_path, name))
            continue
        new, dst = new_path.read_bytes(), root / rel(name)
        if dst.is_file():
            have = _sha(dst.read_bytes())
            if have == _sha(new):
                state[name] = have
                continue
            if have != state.get(name):  # not what we installed: the USER's own text
                log.append(KEPT % (name, new_path, name, new_path))
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(new)
        state[name] = _sha(new)
        log.append("skill:  %s" % rel(name))
    if (root / ".mentat").is_dir():  # an installed brain; a bare scaffold gets no state folder
        (root / STATE).parent.mkdir(exist_ok=True)
        (root / STATE).write_bytes((json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return log


def missing(root):
    return [str(rel(n)) for n in SKILLS if not (pathlib.Path(root) / rel(n)).is_file()]


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_skills.py")
    p.add_argument("--lang", required=True, choices=["hu", "en"])
    p.add_argument("--repo", default=".")
    a = p.parse_args(argv)
    print("\n".join(install(pathlib.Path(a.repo), a.lang)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
