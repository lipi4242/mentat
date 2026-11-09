"""flotta-menedzser: `fleet incident claim|release` — a menedzser átveszi (vagy visszaadja) az incidenst.

    claim <id> --as <ágens>     POST /incidents/<id>/claim a menedzser SAJÁT todo-tokenjével
    release <id> --as <ágens>   POST /incidents/<id>/release (feladja; a Worker továbbadja)

A todo-token helye a `mentat-todo`-éval azonos: `~/.config/todo/handles` („ágens=handle”, hiányzó sor:
az ágens neve) és `~/.config/todo/<handle>.token`. Az átvétel eredménye (fence, claim-titok, a
30 perces keret vége, a cél) a `~/.config/fleet/state/claims/<id>.json`-ba kerül (0600): a
végrehajtó (`fleet repair-exec`) innen olvassa. A titok nem jelenik meg a kimenetben.
Kilépés: 0 átvéve/visszaadva · 1 a Worker elutasította / nem elérhető · 2 beállítási hiba.
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from fleet import CONFIG_DIR, flotta_http, flotta_report

CLAIMS = CONFIG_DIR / "state" / "claims"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _todo_dir() -> Path:
    x = os.environ.get("XDG_CONFIG_HOME")
    d = Path(x) / "todo" if x else Path.home() / ".config" / "todo"
    return d if d.is_dir() else Path.home() / ".config" / "todo"


def manager_token(agent: str) -> str | None:
    d = _todo_dir()
    handle = agent
    try:
        for line in (d / "handles").read_text().splitlines():
            k, _, v = line.strip().partition("=")
            if k.strip() == agent and v.strip():
                handle = v.strip()
    except OSError:
        pass
    try:
        return (d / f"{handle}.token").read_text().strip() or None
    except OSError:
        return None


def claim_path(incident: str) -> Path:
    if not ID_RE.match(incident):
        raise ValueError(f"érvénytelen incidens-azonosító: {incident!r}")
    return CLAIMS / f"{incident}.json"


def load_claim(incident: str) -> dict | None:
    try:
        d = json.loads(claim_path(incident).read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("fence"), int) and d.get("claim") else None


def save_claim(incident: str, d: dict) -> Path:
    p = claim_path(incident)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")   # atomikus csere: egy olvasó sosem lát félkész titkot
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(d, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)
    return p


def _setup(a) -> tuple[str, str] | None:
    if not ID_RE.match(a.incident):
        print(f"incident: érvénytelen azonosító: {a.incident!r}", file=sys.stderr)
        return None
    cfg = flotta_report.config()
    tok = manager_token(a.as_agent)
    if cfg is None or not tok:
        print("incident: hiányzik a flotta.env (FLOTTA_URL) vagy a menedzser todo-tokenje "
              f"({_todo_dir()}/<handle>.token)", file=sys.stderr)
        return None
    return cfg[0], tok


def cmd_claim(a, opener=urllib.request.urlopen) -> int:
    s = _setup(a)
    if s is None:
        return 2
    status, res, info = flotta_http.call("POST", s[0], f"/api/flotta/v1/incidents/{a.incident}/claim", s[1], {}, opener)
    res = res or {}
    if status != 200 or not isinstance(res.get("fence"), int) or not res.get("claim"):
        print(f"incident: nem vehető át ({info}{', ' + str(res.get('code')) if res.get('code') else ''})", file=sys.stderr)
        return 1
    keep = {k: res.get(k) for k in ("incident", "target", "box", "fence", "claim", "attempt_until")}
    keep.update(incident=a.incident, **{"as": a.as_agent})
    save_claim(a.incident, keep)
    print(f"átvéve: {res.get('target')} · fence {res['fence']} · a keret vége {res.get('attempt_until')} "
          f"(nincs hosszabbítás). Lépések: fleet repair-exec {a.incident} <lépés> --agent <ágens>")
    return 0


def cmd_release(a, opener=urllib.request.urlopen) -> int:
    s = _setup(a)
    c = load_claim(a.incident)
    if s is None or c is None:
        print("incident: nincs beállítás vagy nincs átvétel ezen a boxon", file=sys.stderr)
        return 2
    status, res, info = flotta_http.call("POST", s[0], f"/api/flotta/v1/incidents/{a.incident}/release", s[1],
                                         {"fence": c["fence"], "claim": c["claim"]}, opener)
    if status != 200:
        print(f"incident: a visszaadás nem sikerült ({info})", file=sys.stderr)
        return 1
    claim_path(a.incident).unlink(missing_ok=True)
    print(f"visszaadva: {a.incident} → {(res or {}).get('state', '?')}")
    return 0


def add_parser(sub) -> None:
    i = sub.add_parser("incident", help="flotta-incidens átvétele / visszaadása menedzserként (flotta-menedzser)")
    is_ = i.add_subparsers(dest="sub", required=True)
    for name, fn, h in (("claim", cmd_claim, "átvétel: 30 perces kísérleti keret + fencing-token"),
                        ("release", cmd_release, "feladás: a lánc következője kapja")):
        x = is_.add_parser(name, help=h)
        x.add_argument("incident"); x.add_argument("--as", dest="as_agent", required=True, metavar="ÁGENS")
        x.set_defaults(fn=fn)
