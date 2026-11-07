"""`fleet secrets audit [--repo DIR …]` — kiszivárgott-e egy leltárban lévő titok.

A leltár fájljaiból folyamaton belül veszi az értékeket (a hash8 egyezését ellenőrizve), és keresi
őket minden ~/.claude*/projects/**/*.jsonl átiratban, a megadott (fogadó) repók munkafájljaiban és
git-történetében (`git log -p --all`). Kimenet: fájl:sor + osztály + kulcsnév + gazda — érték,
részlet és hash SOHA (minta: security/eszkozok/identitas/szken.py). 0 = tiszta, 1 = lelet.
Rövid (<12 karakter) érték nem kereshető megbízhatóan: ezt külön jelzi.
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

from fleet import titok_formatum as F, titok_hely as H
from fleet.titok_leltar import SKIP

MIN_LEN = 12


def needles(inv: dict) -> tuple[list[tuple[str, dict, str]], list[str]]:
    """[(tű, forrás-leírás, kulcsnév)], [rövid kulcsok]. A tű csak memóriában él."""
    out, short = [], []
    for f in inv.get("files", []):
        if f.get("class") in ("atirat", "olvashatatlan") or not Path(f["path"]).is_file():
            continue
        try:
            vals = F.values(Path(f["path"]))
        except OSError:
            continue
        for name, v in vals.items():
            v = v.strip()
            if len(v) < MIN_LEN:
                short.append(f"{f['agent']}:{name}")
                continue
            forms = {v, json.dumps(v)[1:-1]}
            if len(v) > 64:
                body = "".join(ln for ln in v.splitlines() if ln and not ln.startswith("-----"))
                forms |= {body[len(body) // 2 - 16:len(body) // 2 + 16]} if len(body) > 48 else set()
            out += [(n, f, name) for n in forms if len(n) >= MIN_LEN]
    return out, short


def _scan_lines(lines, label, ndl, found):
    for i, line in enumerate(lines, 1):
        for n, f, name in ndl:
            if n in line:
                found.append({"hol": f"{label}:{i}", "osztaly": f["class"], "nev": name, "gazda": f["agent"]})
                break


def _files(root: Path, skip: set[str]):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for x in files:
            p = Path(d) / x
            if str(p.resolve()) not in skip and p.is_file():
                yield p


def audit(repos: list[Path], home: Path | None = None) -> dict:
    home = Path(home or Path.home())
    try:
        inv = json.loads(H.inventory_path(home).read_text())
    except (OSError, ValueError):
        return {"error": "nincs titok-leltár: előbb `fleet secrets scan --agent <ágens>`"}
    ndl, short = needles(inv)
    own = {f["path"] for f in inv.get("files", [])}
    found = []
    targets = [p for r in home.glob(".claude*") for p in (r / "projects").glob("**/*.jsonl")]
    targets += [p for r in repos for p in _files(Path(r), own)]
    for p in targets:
        try:
            with open(p, errors="replace") as fh:
                _scan_lines(fh, str(p).replace(str(home), "~", 1), ndl, found)
        except OSError:
            continue
    for r in repos:
        if (Path(r) / ".git").exists():
            log = subprocess.run(["git", "-C", str(r), "log", "-p", "--all", "--format=commit %H"],
                                 capture_output=True, text=True, errors="replace")
            commit, path = "?", "?"
            for ln in log.stdout.splitlines():
                commit = ln[7:19] if ln.startswith("commit ") else commit
                path = ln[6:] if ln.startswith("+++ b/") else path
                if ln.startswith("+") and not ln.startswith("+++"):
                    before = len(found)
                    _scan_lines([ln], f"{Path(r).name}@git:{commit}:{path}", ndl, found)
                    for x in found[before:]:
                        x["hol"] = x["hol"].rsplit(":", 1)[0]
    return {"leletek": found, "rovid": short, "tuk": len(ndl)}


def report(res: dict) -> str:
    if res.get("error"):
        return res["error"]
    rows = [f"{len(res['leletek'])} lelet ({res['tuk']} keresett forma; értéket nem írok ki)"]
    rows += [f"  {x['hol']}  {x['osztaly']}  {x['nev']}  ({x['gazda']})" for x in res["leletek"]]
    if res["rovid"]:
        rows.append("rövid, nem kereshető: " + ", ".join(res["rovid"]))
    if res.get("onbevallas"):
        rows.append("önbevallás (jóváhagyás --owner-msg nélkül): " + ", ".join(res["onbevallas"]))
    return "\n".join(rows)
