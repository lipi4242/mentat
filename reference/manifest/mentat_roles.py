"""`roles` (write the roles section), `role` (resolve the effective role) and the
pure `roles_errors` check used by mentat_rules.evaluate.

The effective role is MENTAT_ROLE if it is installed, else roles.default; an
uninstalled MENTAT_ROLE is an error, never a silent fallback. mentat_rules
imports this module, so the manifest modules are imported inside the commands
only (no import cycle).
"""
import json
import os
import pathlib
import re
import sys

ROLE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
HERE = pathlib.Path(__file__).resolve().parent
# the shipped templates: vendored next to this file (.mentat/bin/bekotes/), below it
# (.mentat/bin/), or in the reference tree (manifest/ -> bekotes/)
TEMPLATE_DIRS = (HERE / "szerepek", HERE / "bekotes" / "szerepek", HERE.parent / "bekotes" / "szerepek")


def roles_errors(manifest):
    roles = manifest.get("roles") if isinstance(manifest, dict) else None
    if roles is None:
        return []
    if not isinstance(roles, dict):
        return [{"code": "invalid_value", "at": "roles"}]
    errors = []
    installed = roles.get("installed", [])
    if not isinstance(installed, list):
        return [{"code": "invalid_value", "at": "roles.installed"}]
    for i, name in enumerate(installed):
        if not (isinstance(name, str) and ROLE_NAME.fullmatch(name)):
            errors.append({"code": "invalid_value", "at": "roles.installed[%d]" % i})
    default = roles.get("default")
    if default is not None and default not in installed:
        errors.append({"code": "invalid_value", "at": "roles.default"})
    return errors


def roles(args):
    import mentat_manifest as mm
    default = args.default
    extra = [x.strip() for x in args.install.split(",") if x.strip()]
    for name in [default] + extra:
        if not ROLE_NAME.fullmatch(name):
            raise mm.ManifestError("invalid role name: %s" % name)
    installed = [default] + [x for x in dict.fromkeys(extra) if x != default]
    brain = _brain_root(mm.load(args.repo) or {})
    for name in installed:
        if not _resolvable(pathlib.Path(args.repo) / brain, name):
            raise mm.ManifestError(
                "unknown role: %s (no role file %s and no shipped template); write the role "
                "file first, then run this again (reference/roles.md, Custom roles)"
                % (name, pathlib.Path(brain) / "szerepek" / (name + ".md")))
    mm.update("brain", "roles", {"default": default, "installed": installed}, args.repo)
    print("roles written: default %s, installed %s" % (default, ", ".join(installed)))
    return 0


def _brain_root(manifest):
    import mentat_rules as rules
    return rules._get(manifest, "components", "brain", "root") or "."


def _resolvable(brain_root, name):
    """The role guard reads <brain root>/szerepek/<name>.md; the `szerepek` step writes it from a template."""
    return (brain_root / "szerepek" / (name + ".md")).is_file() or any(
        (d / ("%s.%s.md" % (name, lang))).is_file() for d in TEMPLATE_DIRS for lang in ("hu", "en"))


def role(args):
    import mentat_manifest as mm
    import mentat_rules as rules
    manifest = mm.load(args.repo) or {}
    problems = roles_errors(manifest)
    if problems:
        print("error: roles section invalid: " + ", ".join(
            "%s at %s" % (e["code"], e["at"]) for e in problems), file=sys.stderr)
        return 1
    section = rules._dict(manifest.get("roles"))
    default, installed = section.get("default"), section.get("installed") or []
    env = os.environ.get("MENTAT_ROLE")
    if env:
        if env not in installed:
            print("error: MENTAT_ROLE=%s is not an installed role (%s)"
                  % (env, ", ".join(installed) or "none"), file=sys.stderr)
            return 1
        name, source = env, "env"
    else:
        name, source = default, "default"
    out = {"role": name}
    if name is not None:
        root = rules._get(manifest, "components", "brain", "root") or "."
        out.update(source=source, file=str(pathlib.Path(root) / "szerepek" / (name + ".md")))
    if args.json:
        print(json.dumps(out))
    else:
        print(name if name is not None else "(no role)")
    return 0
