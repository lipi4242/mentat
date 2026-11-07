#!/usr/bin/env python3
"""Command line for the brain: write its manifest entries, report status.

    python3 mentat_cli.py init-brain --name NAME --language en|hu \
        --brain-root brain|agy --version X.Y.Z [--repo .]
    python3 mentat_cli.py status [--json] [--repo .]
    python3 mentat_cli.py roles --default NAME [--install a,b,c] [--repo .]
    python3 mentat_cli.py role [--json] [--repo .]     (see mentat_roles.py)

status exit codes: 0 clean, 1 errors, 2 diagnostics only (unknown schema
or unreadable file - nothing may act on the manifest).
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_manifest as mm  # noqa: E402
import mentat_rules as rules  # noqa: E402
import mentat_roles as roles  # noqa: E402

SYNERGY_TEXT = {
    "brain+engine": "the engine reads todos, cases and decisions from the brain",
    "brain+fleet": "the fleet checks that CLAUDE.md loads AGENTS.md",
    "engine+fleet": "the fleet owns the tick schedule and watches last-tick.json",
    "brain+admin": "cases live in the admin, brain files point to them",
    "engine+admin": "the engine reads due cases from the admin",
    "fleet+admin": "the admin shows desired and observed fleet state",
}
ADMIN_HINT = ("admin: not connected (the todo + backlog of Mentat: todos, cases, backlog items; "
              "offer it, see admin/README.md, \"Connect your agent\")")


def init_brain(args):
    root = pathlib.Path(args.repo)
    if not rules.path_inside_repo(args.brain_root):
        raise mm.ManifestError("brain root must be a relative path inside the repo")
    mm.update("brain", "agent", {"name": args.name, "language": args.language}, root)
    mm.update("brain", "components", {"root": args.brain_root}, root)
    mm.update("brain", "cases", {"backend": "markdown"}, root, seed=True)
    mm.update("brain", "installed", args.version, root)
    ignore = root / ".gitignore"
    text = ignore.read_text() if ignore.exists() else ""
    if ".mentat/" not in text.split():
        ignore.write_text(text + ("" if text.endswith("\n") or not text else "\n") + ".mentat/\n")
    print("mentat.json and .mentat/local.json written; .mentat/ is git-ignored")
    return 0


def _element_line(elem, result, manifest):
    declared = elem in rules._dict(manifest.get("components"))
    broken = any(rules._owner(e["at"]) == elem for e in result["errors"])
    if result["present"][elem]:
        return "%s: present" % elem
    if broken:
        return "%s: declared but invalid (see errors)" % elem
    if declared:
        return "%s: declared, not installed on this machine" % elem
    return ADMIN_HINT if elem == "admin" else "%s: not installed" % elem


def guard_line(root, manifest):
    """One line on the role guard when roles are declared, else None."""
    section = rules._dict(manifest.get("roles"))
    if not section:
        return None
    hu = rules._get(manifest, "agent", "language") == "hu"
    if not (root / ".mentat" / "bin" / "bekotes" / "szerep_guard.py").is_file():
        return "szerep-őr: NINCS TELEPÍTVE" if hu else "role guard: NOT INSTALLED"
    env = os.environ.get("MENTAT_ROLE")
    role = env if env in (section.get("installed") or []) else section.get("default")
    return ("szerep-őr: telepítve (%s)" if hu else "role guard: installed (%s)") % role


def status(args):
    root = pathlib.Path(args.repo)
    result = mm.evaluate_root(root)
    code = 2 if result["diagnostic_only"] else (1 if result["errors"] else 0)
    if args.json:
        print(json.dumps(result, indent=2))
        return code
    if result["diagnostic_only"]:
        print("DIAGNOSTICS ONLY - nothing will act on this manifest:")
    else:
        manifest = mm.load(root)
        print("Elements:")
        for elem in rules.ELEMENTS:
            print("  " + _element_line(elem, result, manifest))
        line = guard_line(root, manifest)
        if line:
            print("  " + line)
        print("Synergies:")
        for pair, live in result["synergies"].items():
            print("  %s: %s - %s" % (pair, "on" if live else "off", SYNERGY_TEXT[pair]))
    for err in result["errors"]:
        print("  error: %s at %s" % (err["code"], err["at"]))
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mentat_cli.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init-brain")
    for flag in ("--name", "--language", "--brain-root", "--version"):
        init.add_argument(flag, required=True)
    stat = sub.add_parser("status")
    stat.add_argument("--json", action="store_true")
    rl = sub.add_parser("roles")
    rl.add_argument("--default", required=True)
    rl.add_argument("--install", default="", help="comma-separated; REPLACES the "
                    "installed list (default is always included)")
    ro = sub.add_parser("role")
    ro.add_argument("--json", action="store_true")
    for p in (init, stat, rl, ro):
        p.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    try:
        if args.cmd in ("roles", "role"):
            return getattr(roles, args.cmd)(args)
        return init_brain(args) if args.cmd == "init-brain" else status(args)
    except mm.ManifestError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
