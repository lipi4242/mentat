"""Availability is observed, never declared: the manifest plus a cheap, read-only probe per
capability. Each result names exactly what the probe saw.

    on        the probe saw it here (and every prerequisite is on)
    degraded  the probe saw it, but a prerequisite is not on
    available not here yet, every prerequisite is on: it can be switched on now
    off       not here, and a prerequisite is missing, or it is not shipped yet (planned)
    unknown   the probe could not run

A probe never reads a secret: `env_key` looks at key NAMES in the environment and .env only.
"""
import json
import os
import pathlib
import shutil
import time


def _json(p):
    try:
        doc = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _dig(doc, dotted):
    for part in dotted.split("."):
        doc = doc.get(part) if isinstance(doc, dict) else None
    return doc


def _env_keys(root):
    keys = set(os.environ)
    try:
        for ln in (root / ".env").read_text(encoding="utf-8").splitlines():
            name = ln.strip().removeprefix("export ").split("=", 1)[0].strip()
            if "=" in ln and name and not name.startswith("#"):
                keys.add(name)
    except OSError:
        pass
    return keys


class Prober:
    def __init__(self, root, entries):
        self.root = pathlib.Path(root)
        self.manifest = _json(self.root / "mentat.json")
        self.local = _json(self.root / ".mentat" / "local.json")
        self.engine = (self.manifest.get("components") or {}).get("engine")
        self.by_id = {e["id"]: e for e in entries}
        self.done = {}
        self.at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _probe(self, p):
        kind, arg = next(iter(p.items()))
        if kind == "bin":
            return (self.root / ".mentat" / "bin" / arg).is_file(), ".mentat/bin/%s present" % arg
        if kind == "component":
            return arg in (self.manifest.get("components") or {}), "mentat.json components.%s" % arg
        if kind == "plugin":
            plugins = (self.engine or {}).get("plugins") or []
            return arg in plugins, "mentat.json components.engine.plugins has %s" % arg
        if kind == "engine_cfg":
            v = _dig(self.engine or {}, arg)
            ok = v == p["equals"] if "equals" in p else bool(v)
            return ok, "mentat.json components.engine.%s%s" % (arg, " = %s" % p["equals"] if "equals" in p else " set")
        if kind == "local":
            return bool(_dig(self.local, arg)), ".mentat/local.json %s set" % arg
        if kind == "manifest":
            return bool(_dig(self.manifest, arg)), "mentat.json %s set" % arg
        if kind == "module":
            base = self.root / pathlib.Path((self.engine or {}).get("path") or "anytime_engine").parent
            pkg, _, mod = arg.partition(".")
            rel = "%s/%s.py" % (pkg, mod or "__init__")
            return (base / rel).is_file(), "%s on disk" % rel
        if kind == "env_key":
            return arg in _env_keys(self.root), "%s set in the environment or .env (value not read)" % arg
        if kind == "which":
            return bool(shutil.which(arg)), "%s on PATH" % arg
        if kind == "own":
            return (self.root / arg).exists(), "%s exists" % arg
        if kind == "doc":
            return None, "documentation: nothing to switch on"
        if kind == "planned":
            return None, "planned: not shipped yet"
        raise ValueError("unknown probe: %s" % kind)

    def state(self, cid, seen=()):
        if cid in self.done:
            return self.done[cid]
        e = self.by_id.get(cid)
        if e is None or cid in seen:
            return {"availability": "unknown", "probe": "no such capability: %s" % cid, "requires": []}
        reqs = [{"id": r, "availability": self.state(r, seen + (cid,))["availability"]} for r in e["requires"]]
        reqs_on = all(r["availability"] == "on" for r in reqs)
        try:
            ok, text = self._probe(e["probe"])
        except (OSError, ValueError, TypeError) as exc:
            ok, text, avail = None, "probe failed: %s" % exc, "unknown"
        else:
            if ok:
                avail = "on" if reqs_on else "degraded"
            elif e.get("lifecycle") == "planned":
                avail = "off"
            else:
                avail = "available" if reqs_on else "off"
        self.done[cid] = {"availability": avail, "probe": text, "observed_at": self.at, "requires": reqs}
        return self.done[cid]
