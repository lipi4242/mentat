"""flotta-menedzser: `fleet managers check|publish` — a menedzser-hozzárendelés egyetlen kiadója.

    check   [--file F] [--target agent:<a>@<box> | box:<box>]   validál; a célra a lánc előnézete
    publish [--file F] [--dry-run]                                 feltölti a Workerbe (PUT /managers)

A feltöltés KÜLÖN, config-író tokennel megy: `~/.config/fleet/flotta-config.env` (FLOTTA_URL +
FLOTTA_CONFIG_TOKEN, a token `flotta:config` jogú). A box jelentő tokenje (flotta.env) itt nem
használható, és a Worker sem fogadja el. A token értéke sehol nem jelenik meg.
Kilépés: 0 rendben · 1 elutasítva / elavult verzió / nem elérhető · 2 hibás fájl vagy beállítás.
"""
from __future__ import annotations
import sys
import urllib.request
from pathlib import Path

from fleet import CONFIG_DIR, alerts, flotta_http, managers_file as mf

CONFIG_ENV = CONFIG_DIR / "flotta-config.env"


def config() -> tuple[str, str] | None:
    env = alerts._env_from_file(CONFIG_ENV)
    url, tok = env.get("FLOTTA_URL", "").rstrip("/"), env.get("FLOTTA_CONFIG_TOKEN", "")
    from fleet.flotta_report import _url_ok   # https; http csak a saját gépre — a config-token sem megy titkosítatlanul
    return (url, tok) if _url_ok(url) and tok else None


def _load(a) -> dict | None:
    try:
        return mf.load(Path(a.file) if a.file else None)
    except mf.ManagersError as e:
        for p in e.problems:
            print(f"managers: {p}", file=sys.stderr)
        return None


def _line(m: dict) -> str:
    return f"  {m['rank']}. {m['handle']} ({m['agent']}) · {m['scope']}"


def cmd_check(a) -> int:
    doc = _load(a)
    if doc is None:
        return 2
    print(f"managers: rendben — v{doc['version']}, {len(doc['managers'])} hozzárendelés ({doc['fleet']})")
    if a.target:
        t = a.target
        agent, box = (t[len("agent:"):].split("@", 1) + [""])[:2] if t.startswith("agent:") else (None, t[len("box:"):])
        if not box:
            print("--target: agent:<ágens>@<box> vagy box:<box>", file=sys.stderr)
            return 2
        ch = mf.chain(doc["managers"], agent, box)
        print(f"lánc ({t}, elérés és alkalmasság nélkül — azt a Worker szűri):")
        print("\n".join(_line(m) for m in ch) or "  ÜRES → ember-kell + e-mail")
    return 0


def publish(doc: dict, cfg: tuple[str, str], opener=urllib.request.urlopen) -> tuple[int, str]:
    url, tok = cfg
    body = {"version": doc["version"], "fleet": doc["fleet"], "managers": doc["managers"]}
    status, res, info = flotta_http.call("PUT", url, "/api/flotta/v1/managers", tok, body, opener)
    res = res or {}
    if status == 200:
        return 0, f"managers: v{res.get('version', doc['version'])} " + ("változatlan" if res.get("unchanged") else "kiadva")
    if status == 409 and res.get("code") == "stale":
        return 1, (f"managers: ELUTASÍTVA — elavult verzió (v{doc['version']}); a Workerben v{res.get('current', '?')} él. "
                   "Húzd le a friss fleet-ops-ot, és emeld a version-t")
    if status in (401, 403):
        return 1, f"managers: a token nem jogosult ({info}); `flotta:config` jogú token kell a {CONFIG_ENV}-ben"
    if status is None:
        return 1, (f"managers: a Worker nem érhető el ({info}) — a kimenet ismeretlen (a kiadás akár be is mehetett); "
                   "futtasd újra ugyanezzel a verzióval: ha bement, „változatlan” lesz a válasz")
    return 1, f"managers: elutasítva ({info}): {str(res.get('error', ''))[:200]}"


def cmd_publish(a, opener=urllib.request.urlopen) -> int:
    doc = _load(a)
    if doc is None:
        return 2
    if a.dry_run:
        print(f"--dry-run: ezt adnám ki (v{doc['version']}, {doc['fleet']}); semmi nem ment el")
        print("\n".join(_line(m) for m in doc["managers"]))
        return 0
    cfg = config()
    if cfg is None:
        print(f"managers: nincs kiadói beállítás: {CONFIG_ENV} (FLOTTA_URL + FLOTTA_CONFIG_TOKEN)", file=sys.stderr)
        return 2
    rc, msg = publish(doc, cfg, opener)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


def validate_problems(rdir: Path) -> list[str]:
    """A `fleet validate` része: ha a registry mellett van managers.json, az is legyen ép."""
    p = rdir.parent / "managers.json"
    if not p.is_file():
        return []
    try:
        mf.load(p)
    except mf.ManagersError as e:
        return [f"managers.json: {x}" for x in e.problems]
    return []


def add_parser(sub) -> None:
    m = sub.add_parser("managers", help="flotta-menedzserek: managers.json ellenőrzése és kiadása a Workerbe (flotta-menedzser)")
    ms = m.add_subparsers(dest="sub", required=True)
    x = ms.add_parser("check", help="validál; --target-re a lánc előnézete")
    x.add_argument("--file"); x.add_argument("--target", metavar="agent:<a>@<box>|box:<box>")
    x.set_defaults(fn=cmd_check)
    x = ms.add_parser("publish", help="feltöltés a Workerbe a config-író tokennel (régebbi verziót a Worker elutasít)")
    x.add_argument("--file"); x.add_argument("--dry-run", action="store_true", help="csak kiírja, nem küld")
    x.set_defaults(fn=cmd_publish)
