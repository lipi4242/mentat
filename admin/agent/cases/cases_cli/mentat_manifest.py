# Vendored from the brain 0.3.0 (reference/manifest/mentat_manifest.py).
# Do not edit here; update from the source.
"""Reference reader/writer for mentat.json and .mentat/local.json.

Python stdlib only; vendor this file together with mentat_rules.py.
Spec: reference/mentat-json.md (rules 1-7).

    load(root)                      -> mentat.json as a dict ({} if absent)
    local(root)                     -> .mentat/local.json as a dict ({} if absent)
    present(elem, root)             -> declared, installed here, and valid
    update(elem, section, data, root, seed=False)
                                    -> merge one owned section under the lock
    evaluate_root(root)             -> the conformance result for a repo
"""
import contextlib
import json
import os
import pathlib
import tempfile

import mentat_rules as rules

MANIFEST = "mentat.json"
LOCAL = os.path.join(".mentat", "local.json")
LOCK = os.path.join(".mentat", "lock")

# section -> (file, owner); owner None means "the element named in the call"
SECTIONS = {
    "components": (MANIFEST, None),
    "agent": (MANIFEST, "brain"),
    "cases": (MANIFEST, "cases"),
    "installed": (LOCAL, None),
    "fleet": (LOCAL, "fleet"),
    "admin": (LOCAL, "admin"),
}
SEEDERS = {"cases": {"brain"}}  # may fill missing fields only


class ManifestError(Exception):
    pass


def _read(path):
    """(document or None, unreadable flag)."""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, False
    except (ValueError, OSError):
        return None, True
    return (doc, False) if isinstance(doc, dict) else (None, True)


def load(root="."):
    return _read(pathlib.Path(root) / MANIFEST)[0] or {}


def local(root="."):
    return _read(pathlib.Path(root) / LOCAL)[0] or {}


def _pair(root):
    manifest, bad_m = _read(root / MANIFEST)
    loc, bad_l = _read(root / LOCAL)
    unreadable = MANIFEST if bad_m else (".mentat/local.json" if bad_l else None)
    return manifest, loc, unreadable


def evaluate_root(root="."):
    return rules.evaluate(*_pair(pathlib.Path(root)))


def present(elem, root="."):
    return evaluate_root(root)["present"].get(elem, False)


@contextlib.contextmanager
def _locked(root):
    path = pathlib.Path(root) / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as handle:
        try:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        except ImportError:  # Windows
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        yield  # closing the handle releases the lock


def _write_atomic(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(doc, out, indent=2, ensure_ascii=False)
        out.write("\n")
    os.replace(tmp, path)


def _merge(doc, section, elem, data, seed):
    if section in ("components", "installed"):
        holder, key = doc.setdefault(section, {}), elem
    else:
        holder, key = doc, section
    old = holder.get(key)
    if isinstance(data, dict):
        merged = dict(old) if isinstance(old, dict) else {}
        for k, v in data.items():
            if not (seed and k in merged):
                merged[k] = v
        holder[key] = merged
    elif not (seed and old is not None):
        holder[key] = data


def update(elem, section, data, root=".", seed=False):
    """Merge `data` into the section `elem` owns; refuse anything else."""
    if section not in SECTIONS:
        raise ManifestError("unknown section: %s" % section)
    filename, owner = SECTIONS[section]
    allowed = owner is None or owner == elem or (seed and elem in SEEDERS.get(section, ()))
    if not allowed:
        raise ManifestError("%s does not own %s" % (elem, section))
    root = pathlib.Path(root)
    with _locked(root):
        before = rules.evaluate(*_pair(root))
        if before["diagnostic_only"]:
            raise ManifestError("refusing to write: %s" % before["errors"])
        path = root / filename
        doc, _ = _read(path)
        doc = doc or {"schema": rules.KNOWN_SCHEMA}
        _merge(doc, section, elem, data, seed)
        pair = (doc, _read(root / LOCAL)[0]) if filename == MANIFEST else (_read(root / MANIFEST)[0], doc)
        new = [e for e in rules.evaluate(*pair)["errors"] if e not in before["errors"]]
        if new:
            raise ManifestError("refusing to write: %s" % new)
        _write_atomic(path, doc)

