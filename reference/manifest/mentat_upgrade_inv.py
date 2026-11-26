"""What kind of Mentat install this folder is, from the files alone (nothing written).

inventory(root) -> dict: kind (box / brain / brain+engine / pre-0.5 / none), the installed
versions, the brain root and the folders that already hold the USER's knowledge, the engine
copy, the product blocks of AGENTS.md, git state, and warnings. Kinds:
  box           a fleet agent (mentat.json components.fleet or .mentat/local.json fleet):
                its server upgrades it with `fleet box-upgrade`, not this tool
  brain         mentat.json with components.brain, no engine
  brain+engine  the same with components.engine and its vendored package
  pre-0.5       AGENTS.md but no mentat.json: a brain from before the .mentat/ layout,
                maybe with a vendored anytime_engine/ (VENDORED.md / VERSION / __version__)
  none          no AGENTS.md: nothing to upgrade, FIRST-INSTALL.md is the way
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess

IDS = ("reference-manual", "layers", "brain-dumps", "entities", "files", "frameworks", "claims",
       "large-work", "intake")
RETIRED = ("calendar_reconcile",)  # engine modules a re-sync removes (engine/release/sync-to.sh)
STOP = {"box": "this is a fleet agent on a server: upgrade it there with `fleet box-upgrade --to v%s --dry-run`, "
               "then the same without --dry-run (UPGRADE.md, \"A fleet agent on a server\")",
        "none": "there is no Mentat brain here (no AGENTS.md): use FIRST-INSTALL.md instead"}

SKIP = {".git", ".mentat", "node_modules", ".venv", "venv", "__pycache__", "anytime_engine",
        "anytime_cases", "anytime_todo", "anytime_bekotes", "anytime_calendar"}


def _json(path):
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, encoding="utf-8", errors="replace")


def engine_version(pkg):
    """The vendored engine's version: VERSION (0.3+), VENDORED.md, else __version__."""
    pkg = pathlib.Path(pkg)
    for name, rx in (("VERSION", r"^version=(\S+)"), ("VENDORED.md", r"^Verzi[óo]:\s*(\S+)"),
                     ("__init__.py", r'^__version__ = "([^"]+)"')):
        p = pkg / name
        m = re.search(rx, p.read_text(encoding="utf-8", errors="replace"), re.M) if p.is_file() else None
        if m:
            return m.group(1)
    return None


def knowledge_dirs(root):
    """Top-level folders with a _meta.md index: where the USER's notes live today (kept in place)."""
    return sorted(p.parent.name for p in pathlib.Path(root).glob("*/_meta.md")
                  if p.parent.name not in SKIP and not p.parent.name.startswith("."))


def retired_imports(root):
    """Files outside the engine that import a module the new engine no longer has."""
    out = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for n in names:
            if n.endswith((".py", ".sh")):
                p = pathlib.Path(d) / n
                text = p.read_text(encoding="utf-8", errors="replace")
                if any(re.search(r"anytime_engine[.\s].*%s|%s.*anytime_engine" % (m, m), text) for m in RETIRED):
                    out.append(p.relative_to(root).as_posix())
    return sorted(out)


def inventory(root):
    root = pathlib.Path(root).resolve()
    man, loc = _json(root / "mentat.json"), _json(root / ".mentat" / "local.json")
    comp = man.get("components") if isinstance(man.get("components"), dict) else {}
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    eng = comp.get("engine") if isinstance(comp.get("engine"), dict) else None
    pkg = root / ((eng or {}).get("path") or "anytime_engine")
    has_pkg = (pkg / "__init__.py").is_file()
    if "fleet" in comp or isinstance(loc.get("fleet"), dict):
        kind = "box"
    elif comp.get("brain"):
        kind = "brain+engine" if eng and has_pkg else "brain"
    elif text:
        kind = "pre-0.5"
    else:
        kind = "none"
    inside = git(root, "rev-parse", "--is-inside-work-tree").returncode == 0
    dirty = [l for l in git(root, "status", "--porcelain", "--untracked-files=all", "--", ".").stdout.splitlines()
             if not l[3:].strip('"').startswith(".mentat/")] if inside else []  # the download itself
    brain = comp.get("brain") if isinstance(comp.get("brain"), dict) else {}
    agent = man.get("agent") if isinstance(man.get("agent"), dict) else {}
    lang = agent.get("language") or ("hu" if len(re.findall(r"[áéíóöőúüű]", text.lower())) > 5 else "en")
    warnings = []
    imports = retired_imports(root) if has_pkg else []
    if imports:
        warnings.append("these files import an engine module the new engine removes: " + ", ".join(imports))
    if kind != "box" and comp.get("engine") and not has_pkg:
        warnings.append("mentat.json lists the engine, but its package is missing")
    return {"kind": kind, "root": str(root), "lang": lang, "agent": agent.get("name"),
            "installed": loc.get("installed") if isinstance(loc.get("installed"), dict) else {},
            "brain_root": brain.get("root") or ("agy" if lang == "hu" else "brain"),
            "knowledge": knowledge_dirs(root),
            "engine": {"path": pkg.relative_to(root).as_posix(), "version": engine_version(pkg),
                       "packs": [p for p in (eng or {}).get("plugins", []) if isinstance(p, str)]} if has_pkg else None,
            "blocks": [i for i in IDS if "mentat:managed:start %s -->" % i in text],
            "git": {"repo": inside, "dirty": dirty, "head": git(root, "rev-parse", "-q", "--verify", "HEAD").stdout.strip()},
            "warnings": warnings}


def fingerprint(inv):
    keep = {k: inv[k] for k in ("kind", "installed", "engine", "blocks", "knowledge")}
    keep["head"] = inv["git"]["head"]
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()


def root_of(inv):
    return pathlib.Path(inv["root"])


def blockers(inv, version, lang, agent, bin_dir):
    """The one reason this folder cannot be upgraded now, or None."""
    if inv["kind"] in STOP:
        return STOP[inv["kind"]] % version if "%s" in STOP[inv["kind"]] else STOP[inv["kind"]]
    linked = [r for r in ("AGENTS.md", "CLAUDE.md", ".claude", ".claude/settings.json", ".mentat", ".gitignore",
                          "mentat.json", inv["brain_root"], "anytime_engine", "projects")
              if (root_of(inv) / r).is_symlink()]
    if linked:
        return "these are symbolic links, the upgrade does not write through them: " + ", ".join(linked)
    if not inv["git"]["repo"] or not inv["git"]["head"]:
        return "this folder is not a git repo with a commit: the upgrade needs one for its backup"
    if inv["git"]["dirty"]:
        return ("uncommitted changes (the backup would miss them): %s — ask the USER to save them first "
                "(a commit of their own), then run plan again" % ", ".join(inv["git"]["dirty"][:8]))
    if not (pathlib.Path(bin_dir) / ("scaffold-agents.%s.md" % lang)).is_file():
        return ("the %s files are not downloaded: run the download step of %s" %
                (lang, "UPGRADE.hu.md" if lang == "hu" else "UPGRADE.md"))
    if inv["kind"] == "pre-0.5" and not agent:
        return "a pre-0.5 brain has no recorded agent name: ask the USER, then pass --agent NAME"
    return None
