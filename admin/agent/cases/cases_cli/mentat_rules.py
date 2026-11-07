# Vendored from the brain 0.3.0 (reference/manifest/mentat_rules.py).
# Do not edit here; update from the source.
"""Pure rules of the mentat.json contract: validation, presence, synergies.

No file access here — `evaluate(manifest, local)` takes the two parsed
documents (or None) and returns the same result shape the conformance
fixtures expect. Spec: reference/mentat-json.md.
"""
import ipaddress
import re
from urllib.parse import urlsplit

KNOWN_SCHEMA = 1
ELEMENTS = ("brain", "engine", "fleet", "admin")
PAIRS = ("brain+engine", "brain+fleet", "engine+fleet",
         "brain+admin", "engine+admin", "fleet+admin")
ENUMS = {
    ("components", "engine", "schedule_owner"): ("engine", "fleet"),
    ("cases", "backend"): ("markdown", "admin"),
}
PATH_FIELDS = (("brain", "root"), ("engine", "path"))
DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _dict(value):
    return value if isinstance(value, dict) else {}


def _get(doc, *keys):
    for key in keys:
        doc = _dict(doc).get(key)
    return doc


def path_inside_repo(value):
    """True for a non-empty relative path that cannot leave the repo."""
    if not isinstance(value, str) or not value.strip():
        return False
    parts = re.split(r"[\\/]+", value)
    if value.startswith(("/", "\\", "~")) or re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in parts


def _is_ip(host):
    try:
        ipaddress.ip_address((host or "").strip("[]"))
        return True
    except ValueError:
        return False


def _endpoints(doc, at, out):
    for key, value in _dict(doc).items():
        here = "%s.%s" % (at, key) if at else key
        if isinstance(value, dict):
            _endpoints(value, here, out)
        elif key == "url" or (isinstance(value, str) and "://" in value):
            out.append({"code": "endpoint_in_manifest", "at": here})


def _schema_errors(manifest, local):
    errors = []
    for doc, at in ((manifest, "schema"), (local, "local.schema")):
        if doc is not None and _dict(doc).get("schema") != KNOWN_SCHEMA:
            errors.append({"code": "schema_unknown", "at": at})
    return errors


def _manifest_errors(manifest):
    errors = []
    comps = _dict(_get(manifest, "components"))
    for elem, field in PATH_FIELDS:
        if elem in comps and field in _dict(comps[elem]):
            if not path_inside_repo(comps[elem][field]):
                errors.append({"code": "path_outside_repo",
                               "at": "components.%s.%s" % (elem, field)})
    plugins = _get(comps, "engine", "plugins") or []
    for i, name in enumerate(plugins if isinstance(plugins, list) else [None]):
        if not (isinstance(name, str) and DOTTED.match(name)):
            errors.append({"code": "plugin_invalid",
                           "at": "components.engine.plugins[%d]" % i})
    for keys, allowed in ENUMS.items():
        value = _get(manifest, *keys)
        if value is not None and value not in allowed:
            errors.append({"code": "invalid_value", "at": ".".join(keys)})
    _endpoints(manifest, "", errors)
    return errors


def _local_errors(local):
    errors = []
    if _is_ip(_get(local, "fleet", "host")):
        errors.append({"code": "ip_address", "at": "local.fleet.host"})
    url = _get(local, "admin", "url")
    if isinstance(url, str) and _is_ip(urlsplit(url).hostname):
        errors.append({"code": "ip_address", "at": "local.admin.url"})
    return errors


def _owner(at):
    """Which element an error disables (None: no element)."""
    m = re.match(r"^(?:components|local)\.(brain|engine|fleet|admin)\b", at)
    return m.group(1) if m else None


def _installed_here(elem, local):
    if elem == "admin":
        return bool(_get(local, "admin", "url"))
    return bool(_get(local, "installed", elem))


def evaluate(manifest, local, unreadable=None):
    """Return {diagnostic_only, errors, present, synergies}.

    `manifest`/`local` are parsed documents or None when the file is absent;
    `unreadable` names a file that exists but is not a JSON object.
    """
    errors = []
    if unreadable:
        errors.append({"code": "unreadable", "at": unreadable})
    errors += _schema_errors(manifest, local)
    diagnostic_only = bool(errors)
    if not diagnostic_only:
        errors += _manifest_errors(manifest) + _local_errors(local)
    broken = {_owner(e["at"]) for e in errors}
    comps = _dict(_get(manifest, "components"))
    present = {e: (not diagnostic_only and e in comps and e not in broken
                   and _installed_here(e, local)) for e in ELEMENTS}
    backend = _get(manifest, "cases", "backend")
    if not diagnostic_only and backend == "admin" and not present["admin"]:
        errors.append({"code": "cases_backend_unavailable", "at": "cases.backend"})
    synergies = {}
    for pair in PAIRS:
        a, b = pair.split("+")
        live = present[a] and present[b]
        synergies[pair] = live and (pair != "brain+admin" or backend == "admin")
    errors.sort(key=lambda e: (e["at"], e["code"]))
    return {"diagnostic_only": diagnostic_only, "errors": errors,
            "present": present, "synergies": synergies}
