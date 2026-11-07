"""Role-restricted sources: their facts never go into the shared map files.

A source is restricted when an installed role's `Read(<glob>)` deny matches its
path (e.g. fejleszto `Read(**/bank/**)` and the live source `~/bank/x.csv`). The
guard keeps that role away from the source file; this keeps it away from the
facts derived from it too: they live under <biz>/<folder>/, where <folder> is the
literal directory of the matching glob, so the same deny covers them.
"""
import os
import pathlib

import hely
import mentat_rules as rules
import szerep_rules as sr


def _role_denies(repo):
    """{role: [Read globs]} for the installed roles (a malformed role file is skipped)."""
    root = hely.brain_root(repo)
    manifest = hely.read_json(repo / "mentat.json") or {}
    section = rules._dict(manifest.get("roles"))
    names = [section.get("default")] + list(section.get("installed") or [])
    out = {}
    for n in {x for x in names if isinstance(x, str)}:
        p = repo / root / "szerepek" / (n + ".md")
        try:
            deny = sr.parse_deny(p.read_text(encoding="utf-8"))
        except (OSError, sr.GuardError):
            continue
        out[n] = [m.group(2) for m in map(sr.RULE.match, deny) if m and m.group(1) == "Read"]
    return out


def _folder(glob):
    """The literal directory a glob names: `**/bank/**` -> `bank`."""
    parts = [p for p in glob.split("/") if p and not set("*?[") & set(p)]
    return parts[-1] if parts else None


def restricted(repo, cfg):
    """{source name: folder} for every source some installed role may not Read."""
    repo = pathlib.Path(repo)
    denies = _role_denies(repo)
    out = {}
    for s in (cfg or {}).get("sources") or []:
        path = s.get("path") if isinstance(s, dict) else None
        if not isinstance(path, str) or not path:
            continue
        full = os.path.expanduser(path) if path.startswith("~") else str(repo / path)
        for globs in denies.values():
            for g in globs:
                if sr.match("Read(%s)" % g, "Read", {"file_path": full}, repo):
                    out[s.get("name")] = _folder(g) or "korlatozott"
                    break
            if s.get("name") in out:
                break
    return out
