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
    mm.update("brain", "roles", {"default": default, "installed": installed}, args.repo)
    print("roles written: default %s, installed %s" % (default, ", ".join(installed)))
    return 0


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
