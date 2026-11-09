"""`fleet secrets scan --agent A [--agent B …]` — titok-leltár, értékek nélkül.

Hol keres: az ágens repója, ~/.config/<a>/, ~/.claude-<a>/, <repó>/.mentat/, a systemd --user
unitok `EnvironmentFile=` fájljai. Mi számít: fájlnév-heurisztika (*.env, .env*, *key*, *token*,
*secret*, *credential*, *.pem, id_*, *service-account*.json, a .bak*/.prev* változatokkal) és a
tartalom bizonyítéka (titok_jelolt.py); a fájlmód egyedül soha — a privát, bizonyíték nélküli
ismeretlen fájl „átnézendő" (`review`: kiírva, a kapu nem tiltja).
Minden ~/.claude*/projects/ (és file-history/) „atirat": az egész titoktár.
Kimenet: ~/.mentat/titkok/leltar.json (0600, atomikus; a többi ágens korábbi sorai maradnak) és
egy táblázat. A titok-kapu (titok_kapu.py) ebből tudja, mit nem nyithat meg senki.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

from fleet import titok_formatum as F, titok_hely as H, titok_jelolt as J

SKIP = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", "plugins", "cache"}
ATIRAT = ("projects", "file-history", "shell-snapshots")


def _walk(root: Path):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not (Path(d) == root and x in ATIRAT and
                                                              root.name.startswith(".claude"))]
        for f in files:
            p = Path(d) / f
            kind = J.classify(p) if p.is_file() else None
            if kind:
                yield kind, p


def _atirat(home: Path) -> list[dict]:
    out = []
    for r in sorted(home.glob(".claude*")):
        for sub in ATIRAT:
            if (r / sub).is_dir():
                out.append({"path": str((r / sub).resolve()), "class": "atirat", "agent": "*", "dir": True})
    return out


def scan(agents: list[str], home: Path | None = None, repos: dict | None = None) -> dict:
    home = Path(home or Path.home())
    files, review, seen = [], [], set()
    for a in agents:
        found = [(label, k, p) for label, root in H.agent_roots(a, (repos or {}).get(a), home) for k, p in _walk(root)]
        found += [("unit EnvironmentFile", "titok", p) for p in H.unit_env_files(a, home) if p.is_file()]
        for label, kind, p in sorted(found, key=lambda x: x[1] != "titok"):  # a titok-ítélet nyer
            real = p.resolve()
            if real in seen:
                continue
            seen.add(real)
            if kind == "atnezendo":  # 11-07: kiírjuk, de a kapu NEM tiltja (a kapu csak a `files`-t olvassa)
                review.append({"path": str(real), "agent": a, "where": label, "shown": str(p)})
                continue
            d = F.describe(real)
            d.update({"agent": a, "where": label, "shown": str(p)})
            if p.is_symlink():
                d["symlink"] = True
            files.append(d)
    return {"schema": 1, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "agents": sorted(agents),
            "files": files + _atirat(home), "review": review}


def save(inv: dict, home: Path | None = None) -> Path:
    path = H.inventory_path(home)
    try:
        old = json.loads(path.read_text())
    except (OSError, ValueError):
        old = {}
    keep = [f for f in old.get("files", []) if f.get("class") != "atirat" and f.get("agent") not in inv["agents"]]
    keep_rev = [f for f in old.get("review", []) if f.get("agent") not in inv["agents"]]
    merged = {**inv, "review": keep_rev + inv.get("review", []), "agents": sorted(set(old.get("agents", [])) | set(inv["agents"])), "files": keep + inv["files"]}
    return H.write_atomic(path, json.dumps(merged, ensure_ascii=False, indent=1) + "\n")


def table(inv: dict, home: Path | None = None) -> str:
    h = str(Path(home or Path.home()))
    rows = ["%-12s %-10s %-6s %7s  %-46s %s" % ("ágens", "osztály", "mód", "méret", "hely", "nevek (érték nélkül)")]
    for f in inv["files"]:
        if f.get("class") == "atirat":
            continue
        names = [k["name"] for k in f.get("keys", [])] or f.get("fields") or f.get("pem") or []
        extra = " [private_key]" if f.get("private_key") else ""
        extra += " [symlink]" if f.get("symlink") else ""
        rows.append("%-12s %-10s %-6s %7s  %-46s %s%s" % (f["agent"], f["class"], f["mode"][-3:], f["size"],
                                                        f["shown"].replace(h, "~", 1), ", ".join(names)[:80], extra))
    at = [f["path"].replace(h, "~", 1) for f in inv["files"] if f.get("class") == "atirat"]
    rows.append("\nátiratok (egészükben titoktár, senki nem olvassa/másolja): " + (", ".join(at) or "nincs"))
    rev = [f["shown"].replace(h, "~", 1) for f in inv.get("review", [])]
    if rev:
        rows.append("átnézendő (privát, de nincs titok-bizonyíték; a kapu NEM tiltja): " + ", ".join(rev))
    rows.append("%d titokfájl. A titok-kapu ezeket ettől kezdve nem engedi megnyitni." %
                sum(1 for f in inv["files"] if f.get("class") != "atirat"))
    return "\n".join(rows)
