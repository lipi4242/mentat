"""`fleet join` / `fleet upgrade` — egy ágens-repó belépése a flottába.

Amit a repó kap (2.3 a designban):
  .claude/fleet.json            — mi ő és mit használ (komponens-verziók)
  .claude/rules/fleet.md        — mindig betöltött szabályfájl, verziós fejléccel
  .claude/settings.json         — a fleet plugin engedélyezése (csak a saját kulcsaink)

Tranzakciós elvek (Codex F0-review, 3. rés): csak a saját kulcsainkhoz
nyúlunk a settings.json-ban; a rules-fájl hash-ét a manifest őrzi, és
frissítéskor egy kézzel módosított fájlt NEM írunk felül, hanem `.new`
mellé tesszük (és a verziót nem léptetjük); minden írás temp + rename, egy
tranzakcióban, ami bukáskor mindent visszaállít.

A mentat.json-szinergiák (LG1 spec): `fleet.join_mentat`.
"""
from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path

from fleet import __version__, TEMPLATES_DIR
from fleet import components
from fleet import mentat_manifest as mm
from fleet.join_mentat import join_mentat
from fleet.names import is_valid_agent_name
from fleet.txn import Txn, run_cmd

from fleet.plugin_source import load_json as _load_json, MARKETPLACE_NAME, PLUGIN_KEY, legacy_plugins, merge_local, parse as parse_source  # noqa: E402,F401

#: A forrás egyetlen helye: `fleet.plugin_source` (PUBLIC_REPO; fork esetén
#: FLEET_MARKETPLACE_REPO=<owner>/<repo>). Privát repónál a telepítés
#: hitelesítést kér — ezt a `fleet.plugin_install` érthetően jelzi.
MARKETPLACE_REPO = parse_source(None).add_arg
DEFAULT_MARKETPLACE = {"source": "github", "repo": MARKETPLACE_REPO}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def render_rules(agent: str, *, template: str | None = None) -> str:
    text = template if template is not None else (TEMPLATES_DIR / "rules" / "fleet.md.tmpl").read_text()
    return text.replace("@@AGENT@@", agent).replace("@@FLEET_VERSION@@", __version__)


def manifest_path(repo: Path) -> Path:
    return Path(repo) / ".claude" / "fleet.json"


def read_manifest(repo: Path) -> dict | None:
    try:
        return json.loads(manifest_path(repo).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def merge_settings(existing: dict, *, marketplace: dict = DEFAULT_MARKETPLACE) -> dict:
    """Pure: a fleet plugin bejegyzései a project settings.json-ban, minden
    más kulcs érintetlenül. Egy régi „fleet” plugint (`legacy_plugins`) kikapcsol,
    de a marketplace-bejegyzését nem törli."""
    out = json.loads(json.dumps(existing))  # deep copy
    out.setdefault("extraKnownMarketplaces", {})[MARKETPLACE_NAME] = {"source": marketplace}
    for k in legacy_plugins(out):
        out["enabledPlugins"][k] = False
    out.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
    return out


def join(repo: Path, *, agent: str, brain: str | None = None, reducer: str | None = None,
         marketplace: dict = DEFAULT_MARKETPLACE, now: datetime.date | None = None,
         plugin_source: str | None = None, fix_claude_md: bool = False,
         unit_dir: Path | None = None, host: str | None = None, run=run_cmd) -> dict:
    """Belépés a flottába, tranzakcióban: bármely lépés bukásakor
    minden érintett fájl (a mentat-fájlok is) visszaáll."""
    repo = Path(repo)
    if not is_valid_agent_name(agent):
        raise ValueError(f"nem érvényes ágensnév: {agent!r}")
    if not (repo / ".git").exists():
        raise ValueError(f"nem git repó: {repo}")
    src = parse_source(plugin_source)  # rossz kapcsolónál még nem írtunk semmit
    t = Txn(run)
    try:
        rules = render_rules(agent)
        rules_path = repo / ".claude" / "rules" / "fleet.md"
        t.write(rules_path, rules)
        settings_path = repo / ".claude" / "settings.json"
        existing = _load_json(settings_path)
        t.write(settings_path, json.dumps(merge_settings(existing, marketplace=marketplace),
                                          indent=2, ensure_ascii=False) + "\n")
        local_path = repo / ".claude" / "settings.local.json"
        if src.local is not None:
            t.write(local_path, json.dumps(merge_local(_load_json(local_path), src.local),
                                           indent=2, ensure_ascii=False) + "\n")
        notes = join_mentat(t, repo, agent=agent, fix_claude_md=fix_claude_md,
                            unit_dir=unit_dir, host=host, run=run)
        old = read_manifest(repo) or {}
        found = components.detect(repo)
        manifest = {
            "agent": agent,
            "joined": old.get("joined") or (now or datetime.date.today()).isoformat(),
            "components": {
                "fleet": __version__,
                "brain": brain or found["brain"] or old.get("components", {}).get("brain"),
                "reducer": reducer or found["reducer"] or old.get("components", {}).get("reducer"),
            },
            "rules_sha": _sha(rules),
            "updated": (now or datetime.date.today()).isoformat(),
        }
        t.write(manifest_path(repo), json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    except Exception:
        t.rollback()
        raise
    return {"repo": str(repo), "agent": agent, "manifest": manifest, "notes": notes,
            "wrote": [str(rules_path), str(settings_path), str(manifest_path(repo))]}


def upgrade(repo: Path, now: datetime.date | None = None) -> dict:
    """A rules-fájl frissítése. Ha helyi szerkesztés miatt az új változat
    `.new`-ként marad, az NEM siker: a manifest a ténylegesen telepített
    verziót tartja, és az eredmény `ok: False`."""
    repo = Path(repo)
    m = read_manifest(repo)
    if not m:
        raise ValueError("nincs .claude/fleet.json — előbb `fleet join`")
    rules_path = repo / ".claude" / "rules" / "fleet.md"
    new = render_rules(m["agent"])
    result = {"agent": m["agent"], "from": m["components"].get("fleet"), "to": __version__, "ok": True}
    current = rules_path.read_text() if rules_path.exists() else ""
    t = Txn()
    try:
        if current and _sha(current) != m.get("rules_sha"):
            t.write(rules_path.with_suffix(".md.new"), new)
            result.update(ok=False, to=m["components"].get("fleet"),
                          rules="helyi módosítás — az új verzió fleet.md.new-ként mellé került; "
                                "fésüld össze kézzel, töröld a .new-t, és futtasd újra az upgrade-et")
        else:
            t.write(rules_path, new)
            result["rules"] = "frissítve"
            m["components"]["fleet"] = __version__
            m["rules_sha"] = _sha(new)
        m["updated"] = (now or datetime.date.today()).isoformat()
        settings_path = repo / ".claude" / "settings.json"
        existing = json.loads(settings_path.read_text() or "{}") if settings_path.exists() else {}
        t.write(settings_path, json.dumps(merge_settings(existing), indent=2, ensure_ascii=False) + "\n")
        if legacy_plugins(existing):
            result["plugin_migration"] = {"disabled": legacy_plugins(existing), "enabled": PLUGIN_KEY,
                                          "run_on_box_before_merge": f"fleet plugin install {m['agent']}"}
        t.write(manifest_path(repo), json.dumps(m, indent=2, ensure_ascii=False) + "\n")
        if result["ok"] and mm.load(repo) is not None and mm.schema_ok(mm.load(repo)):
            t.guard(repo / ".mentat" / "local.json")
            mm.update(repo, "fleet", "installed", __version__)
    except Exception:
        t.rollback()
        raise
    return result
