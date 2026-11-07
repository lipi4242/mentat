"""`fleet secrets scan --agent A [--agent B …]` — titok-leltár, értékek nélkül.

Hol keres: az ágens repója, ~/.config/<a>/, ~/.claude-<a>/, <repó>/.mentat/, a systemd --user
unitok `EnvironmentFile=` fájljai. Mi számít: fájlnév-heurisztika (*.env, .env*, *key*, *token*,
*secret*, *credential*, *.pem, id_*, *service-account*.json, a .bak*/.prev* változatokkal) és
minden 0600-as fájl. Minden ~/.claude*/projects/ (és file-history/) „atirat": az egész titoktár.
Kimenet: ~/.mentat/titkok/leltar.json (0600, atomikus; a többi ágens korábbi sorai maradnak) és
egy táblázat. A titok-kapu (titok_kapu.py) ebből tudja, mit nem nyithat meg senki.
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path

from fleet import titok_formatum as F, titok_hely as H

STRONG = re.compile(r"^(\.env.*|.*\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_[a-z0-9]+|.*service[-_]?account.*\.json|"
                    r"\.?credentials.*)$", re.I)
WORD = re.compile(r"key|token|secret|credential|passw", re.I)
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".md", ".rst", ".sh", ".go", ".rs", ".rb",
            ".java", ".html", ".css", ".txt", ".lock"}
SKIP = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", "plugins", "cache"}
ATIRAT = ("projects", "file-history", "shell-snapshots")


def candidate(p: Path) -> bool:
    name = re.sub(r"\.(bak|prev|old|orig)([.-].*)?$", "", p.name)
    if name.endswith((".example", ".sample", ".template", ".pub")):
        return False
    try:
        private = (p.stat().st_mode & 0o077) == 0
    except OSError:
        return False
    if STRONG.match(name):
        return True
    if Path(name).suffix.lower() not in CODE_EXT and WORD.search(name):
        return True
    return private and not state_json(p)


#: A futásidejű állapot lease-azonosítója, nem hitelesítő (heartbeat `owner_token`).
LEASE_FIELDS = {"owner_token", "lease_token"}


def state_json(p: Path) -> bool:
    """`data/state/*.json`: az atomikus írás (mkstemp) miatt 0600, de futásidejű állapot
    (tick-idő, heartbeat). Csak akkor nem titok, ha JSON, és nincs benne titok-jellegű mező
    a lease-azonosítón kívül (11-07: a leltár a last-tick.json-t és a heartbeatet is tiltotta)."""
    if p.suffix != ".json" or p.parent.name != "state" or p.parent.parent.name != "data":
        return False
    try:
        cls, data = F.kind(p.read_bytes()[:F.MAX])
    except OSError:
        return False
    return cls == "json" and not any(F.SECRET_FIELD.search(k) for k in data if k not in LEASE_FIELDS)


def json_with_secret(p: Path) -> bool:
    """Rejtett konfig-mappában (.mentat, .thufir, ~/.config/<a>) a JSON, ha van titok-jellegű mezője."""
    if p.suffix != ".json" or not (p.parent.name in (".mentat", ".thufir") or p.parent.parent.name == ".config"):
        return False
    try:
        cls, data = F.kind(p.read_bytes()[:F.MAX])
    except OSError:
        return False
    return cls == "json" and any(F.SECRET_FIELD.search(k) for k in data)


def _walk(root: Path):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not (Path(d) == root and x in ATIRAT and
                                                              root.name.startswith(".claude"))]
        for f in files:
            p = Path(d) / f
            if p.is_file() and (candidate(p) or json_with_secret(p)):
                yield p


def _atirat(home: Path) -> list[dict]:
    out = []
    for r in sorted(home.glob(".claude*")):
        for sub in ATIRAT:
            if (r / sub).is_dir():
                out.append({"path": str((r / sub).resolve()), "class": "atirat", "agent": "*", "dir": True})
    return out


def scan(agents: list[str], home: Path | None = None, repos: dict | None = None) -> dict:
    home = Path(home or Path.home())
    files, seen = [], set()
    for a in agents:
        found = [(label, p) for label, root in H.agent_roots(a, (repos or {}).get(a), home) for p in _walk(root)]
        found += [("unit EnvironmentFile", p) for p in H.unit_env_files(a, home) if p.is_file()]
        for label, p in found:
            real = p.resolve()
            if real in seen:
                continue
            seen.add(real)
            d = F.describe(real)
            d.update({"agent": a, "where": label, "shown": str(p)})
            if p.is_symlink():
                d["symlink"] = True
            files.append(d)
    return {"schema": 1, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "agents": sorted(agents),
            "files": files + _atirat(home)}


def save(inv: dict, home: Path | None = None) -> Path:
    path = H.inventory_path(home)
    try:
        old = json.loads(path.read_text())
    except (OSError, ValueError):
        old = {}
    keep = [f for f in old.get("files", []) if f.get("class") != "atirat" and f.get("agent") not in inv["agents"]]
    merged = {**inv, "agents": sorted(set(old.get("agents", [])) | set(inv["agents"])), "files": keep + inv["files"]}
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
    rows.append("%d titokfájl. A titok-kapu ezeket ettől kezdve nem engedi megnyitni." %
                sum(1 for f in inv["files"] if f.get("class") != "atirat"))
    return "\n".join(rows)
