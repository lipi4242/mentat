#!/usr/bin/env python3
"""The brain's skeleton in one call: idempotent, never overwrites a file.

    python3 mentat_scaffold.py --lang hu|en --base <manual URL>   # create what is missing
    python3 mentat_scaffold.py --lang hu --name <agent name>      # + mentat.json (init-brain)
    python3 mentat_scaffold.py --lang hu --commit                 # first commit, secrets refused
    python3 mentat_scaffold.py --lang hu --check                  # verify only; exit 0 = complete

Creates: git repo, AGENTS.md (with TBD placeholders the intro chat fills),
CLAUDE.md loading it, the brain folders with _meta.md, .gitignore entries.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mentat_scaffold_check import IGNORES, check, git, layout, append_blocks  # noqa: E402

COMMIT_MSG = {"hu": "chore: az agy beállítása (Mentat)",
              "en": "chore: set up the brain (Mentat)"}
LEFT = {"hu": "nem commitoltam: %d fájl változott, amit nem én hoztam létre — nézd meg: git status",
        "en": "not committed: %d changed file(s) I did not create — see: git status"}


def ensure_lines(path, lines, log):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [ln for ln in lines if ln not in text.splitlines()]
    if missing:
        sep = "" if not text or text.endswith("\n") else "\n"
        path.write_text(text + sep + "".join(ln + "\n" for ln in missing), encoding="utf-8")
        log.append("added   %s to %s" % (", ".join(missing), path.name))


def scaffold(root, lang, base):
    log = []
    r = git(root, "rev-parse", "--is-inside-work-tree")
    if r is None:
        log.append("WARNING git is not installed - install it, then run this again")
    elif r.returncode != 0:
        git(root, "init", "-q")
        log.append("created git repo")
    if (root / "AGENTS.md").exists():  # takeover or upgrade: only the missing product blocks go in
        log.append(append_blocks(root / "AGENTS.md", lang, base))
    else:
        if not base:
            raise SystemExit("error: --base <manual URL> is needed to write AGENTS.md")
        tpl = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
        base = base if base.endswith("/") else base + "/"
        text = tpl.replace("{BASE}", base).replace("{LANG}", lang)
        (root / "AGENTS.md").write_text(text, encoding="utf-8")
        log.append("created AGENTS.md")
    ensure_lines(root / "CLAUDE.md", ["@AGENTS.md"], log)
    for rel, text in layout(lang)["dirs"].items():
        meta = root / rel / "_meta.md"
        if not meta.exists():
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text("# %s\n\n%s\n" % (rel, text), encoding="utf-8")
            log.append("created %s/_meta.md" % rel)
    ensure_lines(root / ".gitignore", IGNORES, log)
    hook_guard(root, log)
    return log


def hook_guard(root, log):
    """The read guard from the first session on (.mentat/bin/bekotes/ after step 1)."""
    for d in (HERE / "bekotes", HERE.parent / "bekotes"):
        if (d / "szerep_hook.py").is_file():
            sys.path.insert(0, str(d))
            import szerep_hook
            try:
                szerep_hook.install(root)
                log.append("hooked  .claude/settings.json (szerep-őr)")
            except ValueError as e:
                log.append("WARNING %s - the guard is not hooked" % e)
            return
    log.append("WARNING .mentat/bin/bekotes/ is missing - rerun step 1, the guard is not hooked")


def version(arg):
    if arg:
        return arg
    for cand in (HERE / "release.json", HERE.parent.parent / "release.json"):
        if cand.exists():
            return json.loads(cand.read_text())["version"]
    raise SystemExit("error: no release.json next to this tool - pass --version X.Y.Z")


def init_brain(root, lang, name, ver):
    cmd = [sys.executable, str(HERE / "mentat_cli.py"), "init-brain", "--name", name,
           "--language", lang, "--brain-root", layout(lang)["root"], "--version", ver,
           "--repo", str(root)]
    return subprocess.run(cmd).returncode


def own_files(root, lang):
    """The files this tool writes; the USER's other changes are never swept into its commit."""
    rels = ["AGENTS.md", "CLAUDE.md", ".gitignore", "mentat.json", ".claude/settings.json"]
    rels += ["%s/_meta.md" % d for d in layout(lang)["dirs"]]
    return [r for r in rels if (root / r).exists()]


def commit(root, lang):
    """Commit only this tool's own files (the folder may sit inside a bigger repo)."""
    if git(root, "--version") is None:
        print("STOP git is not installed")
        return 1
    who = [git(root, "config", k).stdout.strip() for k in ("user.name", "user.email")]
    if not all(who):
        print("STOP git user.name/user.email is empty - ask the USER, then set it for this "
              "repo only: git config user.name ...; git config user.email ...")
        return 1
    own = own_files(root, lang)
    # Paths relative to this folder (it may sit inside a bigger repo): changed, deleted,
    # untracked (not ignored), and already staged by the USER.
    changed = set(git(root, "ls-files", "-m", "-d", "-o", "--exclude-standard", "--", ".").stdout.splitlines())
    changed |= set(git(root, "diff", "--cached", "--name-only", "--relative", "--", ".").stdout.splitlines())
    others = sorted(changed - set(own))
    secret = [p for p in others if re.search(r"(^|/)\.env(\.|$)|(^|/)\.mentat/", p)]
    if secret:
        print("STOP secrets would be committed: %s - add them to .gitignore" % ", ".join(secret))
        return 1
    git(root, "add", "--", *own)
    staged = git(root, "diff", "--cached", "--name-only", "--relative", "--", *own).stdout.splitlines()
    if staged:
        git(root, "commit", "-q", "-m", COMMIT_MSG[lang], "--", *own)
    print(git(root, "log", "--oneline", "-1").stdout.strip() or "STOP nothing to commit")
    if others:
        print(LEFT[lang] % len(others))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_scaffold.py")
    p.add_argument("--lang", required=True, choices=["hu", "en"])
    p.add_argument("--repo", default=".")
    p.add_argument("--base", help="manual base URL, e.g. https://raw.githubusercontent.com/.../vX.Y.Z/")
    p.add_argument("--name", help="agent name: also writes mentat.json")
    p.add_argument("--version", help="defaults to release.json next to this tool")
    p.add_argument("--commit", action="store_true")
    p.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    root = pathlib.Path(a.repo)
    if a.check:
        return check(root, a.lang)
    print("\n".join(scaffold(root, a.lang, a.base)))
    if a.name and init_brain(root, a.lang, a.name, version(a.version)) != 0:
        return 1
    return commit(root, a.lang) if a.commit else 0


if __name__ == "__main__":
    sys.exit(main())
