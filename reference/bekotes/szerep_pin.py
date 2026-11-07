"""Repo-root discovery, role resolution and the per-session pin for szerep_guard.py."""
import contextlib
import io
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # the guard imports only its own, protected folder (Codex: imports)
if (HERE.parent / "manifest").is_dir():  # the dev tree; installed, mentat_roles sits next to us
    sys.path.append(str(HERE.parent / "manifest"))
import mentat_roles  # noqa: E402
from szerep_rules import GuardError  # noqa: E402


def _up(start):
    p = pathlib.Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / "mentat.json").is_file():
            return d
    return None


def find_root(data):
    cands = [os.environ.get("CLAUDE_PROJECT_DIR")]
    if HERE.parent.name == "bin" and HERE.parent.parent.name == ".mentat":
        cands.append(HERE.parents[2])
    cands.append(data.get("cwd") or os.getcwd())
    for c in cands:
        found = _up(c) if c else None
        if found:
            return found
    return None


def resolve(root):
    """Shared role resolution; returns {"role", "source", "file"}."""
    try:
        manifest(root)
    except (OSError, ValueError) as e:
        raise GuardError("mentat.json unreadable: %s" % e)
    ns = type("A", (), {"repo": str(root), "json": True})()
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = mentat_roles.role(ns)
    except Exception as e:  # ManifestError and friends
        raise GuardError(str(e))
    if rc != 0:
        raise GuardError(err.getvalue().strip() or "role resolution failed")
    return json.loads(out.getvalue())


def manifest(root):
    return json.loads((root / "mentat.json").read_text())


def safe_sid(sid):
    return sid if isinstance(sid, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", sid) else None


def write_pin(root, sid, role):
    pin = root / ".mentat" / "szerep" / sid
    pin.parent.mkdir(parents=True, exist_ok=True)
    pin.write_text(role + "\n")


def pinned_role(root, sid):
    pin = root / ".mentat" / "szerep" / sid if sid else None
    if pin and pin.is_file() and pin.read_text().strip():
        name = pin.read_text().splitlines()[0].strip()
        if name not in (manifest(root).get("roles") or {}).get("installed", []):
            raise GuardError("pinned role %s is not installed" % name)
        return {"role": name, "file": None}
    res = resolve(root)
    if res["role"] and sid:
        write_pin(root, sid, res["role"])
    return res


def brain_root(root):
    return ((manifest(root).get("components") or {}).get("brain") or {}).get("root") or "."


def role_file(root, res):
    if res.get("file"):
        return root / res["file"]
    return root / brain_root(root) / "szerepek" / (res["role"] + ".md")
