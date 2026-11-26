"""The upgrade's steps: plan (what would change, nothing written) and apply (after the USER's yes).

Every write is additive or product-owned: a backup branch first, then the product blocks of
AGENTS.md (the USER's text around them is kept), the missing skeleton (mentat_scaffold: it never
overwrites a file), mentat.json for a pre-0.5 brain (its notes stay where they are), the engine
re-vendored from the one clone at the release tag (the release's own sync-to.sh, which restores
the old copy on any failure), the role self-image rules (mentat_upgrade_onkep), the installed
version, and one commit of exactly these changes.
"""
import os
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
import mentat_upgrade_blocks as blocks  # noqa: E402
import mentat_upgrade_onkep as onkep  # noqa: E402
from mentat_upgrade_inv import git  # noqa: E402

SECRET = re.compile(r"(^|/)\.env(\.|$)|(^|/)\.mentat/")
CLONE = "~/src/mentat"
PACKS = ("calendar", "cases", "bekotes", "todo")  # engine/release/sync-to.sh --pack


def plan(inv, version, base, lang):
    """[(step, what)] in the order apply runs them."""
    root, out = pathlib.Path(inv["root"]), []
    old = inv["installed"].get("brain") or ("pre-0.5" if inv["kind"] == "pre-0.5" else "?")
    out.append(("backup", "git branch %s at the current commit (nothing else changes on it)" % branch_name(old, version)))
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    _, changed, broken = blocks.refreshed(text, lang, base)
    missing = [b for b in blocks.template_blocks(lang, base) if b not in inv["blocks"]]
    out.append(("agents", "AGENTS.md: product blocks refreshed %s, added at the end %s; your text outside "
                "the markers is kept" % (changed or "none", missing or "none")))
    out += [("agents-broken", "block %s has a missing or doubled marker: left as it is, fix it by hand" % b)
            for b in broken]
    if inv["kind"] == "pre-0.5":
        out.append(("manifest", "mentat.json (agent name, language, brain root %s) and .mentat/ are created; your "
                    "notes stay where they are: %s" % (inv["brain_root"], ", ".join(inv["knowledge"]) or "-")))
    out.append(("skeleton", "missing brain folders, CLAUDE.md line, .gitignore lines and the safety guard hook "
                "are added; no existing file is overwritten (other hooks in .claude/settings.json are kept)"))
    out.append(("skills", "the brain's skills as local Claude Code skills in .claude/skills/ (a skill you edited "
                "is kept), the /whoami and /mentat commands, the status line unless you have one"))
    out.append(("self-image", "the self-image block first in AGENTS.md, from mentat.json roles"))
    if inv["engine"]:
        out.append(("engine", "%s %s -> %s from %s at v%s (the product copy is replaced; your commit and the "
                    "backup branch keep the old one)" % (inv["engine"]["path"], inv["engine"]["version"] or "?",
                                                        version, CLONE, version)))
    for role, action, why, _ in onkep.plan(root, inv["brain_root"], lang):
        out.append(("onkep", "%s: %s — %s" % (role, action, why)))
    out.append(("commit", "one commit: \"chore: Mentat %s -> %s\"" % (old, version)))
    return out


def branch_name(old, new):
    return "mentat-backup/%s-to-%s-%s" % (re.sub(r"[^0-9A-Za-z.-]", "", old) or "old", new,
                                          time.strftime("%Y%m%d-%H%M%S"))


def backup(root, old, new):
    name = branch_name(old, new)
    r = git(root, "branch", name)
    return name if r.returncode == 0 else None


def run(cmd, root, **kw):
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, **kw)


def manifest(root, inv, version, lang, agent):
    cmd = [sys.executable, str(HERE / "mentat_cli.py"), "init-brain", "--name", agent, "--language", lang,
           "--brain-root", inv["brain_root"], "--version", version, "--repo", str(root)]
    r = run(cmd, root)
    return None if r.returncode == 0 else "mentat.json was not written: " + (r.stdout + r.stderr).strip()[-160:]


def sync_args(root):
    """sync-to.sh's arguments: every vendored pack comes along (a minor release moves the packs' engine
    range, so a pack left at the old version would no longer load), recorded in mentat.json or not."""
    out = ["."]
    for pack in PACKS:
        if (pathlib.Path(root) / ("anytime_" + pack) / "__init__.py").is_file():
            out += ["--pack", pack]
    return out


def engine(root, version, src):
    sys.path.append(str(HERE))
    import mentat_init  # its checkout(): the one clone, moved to the tag
    import mentat_init_os as osx
    clone = pathlib.Path(os.path.expanduser(CLONE))
    problem = mentat_init.checkout(clone, "v" + version, src or mentat_init.PRODUCT_REPO)
    if problem:
        return problem
    tag = git(clone, "rev-parse", "-q", "--verify", "v%s^{commit}" % version).stdout.strip()
    if not tag or git(clone, "rev-parse", "HEAD").stdout.strip() != tag or \
            git(clone, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return ("the Mentat copy %s is not exactly the v%s tag (local changes or another commit): nothing "
                "of the engine was run; ask the USER to look at it" % (clone, version))
    r = run(osx.script(clone / "engine" / "sync-to.sh") + sync_args(root), root)
    if r.returncode != 0:
        return "the engine sync stopped (its old copy is back): " + (r.stdout + r.stderr).strip()[-200:]
    r = run([sys.executable, "-m", "anytime_engine.selftest", "-q"], root, timeout=300)
    return None if r.returncode == 0 else "the engine selftest is not green: " + (r.stdout + r.stderr).strip()[-160:]


def ours(path, brain_root, own=()):
    """The paths an upgrade writes (`own`: mentat_scaffold's own files); anything else changed meanwhile
    is not swept into its commit."""
    return path in own or bool(re.match(r"^(AGENTS\.md|CLAUDE\.md|\.gitignore|\.claude/settings\.json|mentat\.json|"
                         r"anytime_[a-z]+/|projects/_meta\.md|%s/)" % re.escape(brain_root.strip("/")), path))


def commit(root, old, version, brain_root, lang):
    import mentat_scaffold
    own = set(mentat_scaffold.own_files(root, lang))
    git(root, "add", "-A", "--", ".")
    staged = git(root, "diff", "--cached", "--name-only", "--relative", "--", ".").stdout.splitlines()
    bad = [p for p in staged if SECRET.search(p) or not ours(p, brain_root, own)]
    if bad:
        git(root, "reset", "-q")
        return None, ("not committed: %s changed but is not the upgrade's (or looks like a secret); the changes "
                      "are in the folder, uncommitted — show the USER `git status`" % ", ".join(bad[:8]))
    msg = "chore: Mentat %s -> %s" % (old, version)
    if staged and git(root, "commit", "-q", "-m", msg).returncode:
        return None, ("not committed: git refused the commit (no git identity on this machine?); the upgrade's "
                      "changes are staged — set `git config user.name` and `git config user.email`, then "
                      "`git commit -m \"%s\"`" % msg)
    return staged, None
