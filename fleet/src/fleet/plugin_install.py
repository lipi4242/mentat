"""A /fleet:* plugin telepítése az ágens repójába (`--scope local`), a claude saját CLI-jével.

A `fleet join` a repó settings.json-jába csak deklarálja a marketplace-t; egy headless
claude ebből NEM telepít (2026-10-31, élő box). A tényleges telepítés itt történik,
az ágens repójában, local scope-pal: a user scope közös fiókon minden ágensnek
bekapcsolná. Ugyanabban a settings.local.json-ban a régi `fleet@*` plugin kikapcsol,
így a régi és az új sosem fut egymás mellett. A telepítés nem-interaktívan, hogy egy hiba szövegesen
látszódjon (és ne egy TUI-ablak álljon a pane-ben). Nem blokkol: a plugin
kényelmi réteg, az ágens nélküle is fut — a hiba egy érthető megjegyzés.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

from fleet import claude_auth
from fleet.plugin_source import PLUGIN_KEY, legacy_plugins, load_json, parse

_PRIVATE_HINTS = ("not found", "authentication", "could not read username", "permission denied",
                  "repository not found", "403", "401")


def _ok(r) -> bool:
    text = ((r.stdout or "") + (r.stderr or "")).lower()
    return r.returncode == 0 or "already" in text


def _why(r, repo: str) -> str:
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    last = text.splitlines()[-1] if text else f"kód {r.returncode}"
    if any(h in text.lower() for h in _PRIVATE_HINTS):
        return (f"a {repo} nem érhető el ({last}) — privát repó? Ezen a gépen git-hitelesítés kell "
                f"hozzá (`gh auth login` + `gh auth setup-git`), vagy FLEET_MARKETPLACE_REPO=<fork>")
    return last


def _workdir(entry: dict, home: Path) -> Path:
    return Path(str(entry.get("workdir") or "").replace("%h", str(home)))


def _enable_local(wd: Path) -> list[str]:
    """settings.local.json: a miénk be, minden más `fleet@*` ki. Csak ha változik, ír (tmp + rename)."""
    path = wd / ".claude" / "settings.local.json"
    local = load_json(path)
    old = sorted(set(legacy_plugins(load_json(wd / ".claude" / "settings.json"))) | set(legacy_plugins(local)))
    want = dict(local.get("enabledPlugins") or {}, **{k: False for k in old}, **{PLUGIN_KEY: True})
    if want != local.get("enabledPlugins"):
        path.parent.mkdir(exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(dict(local, enabledPlugins=want), indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    return old


def install_plugin(entry: dict, *, claude_bin: Path, home: Path, run=claude_auth.run_env,
                   plugin_source: str | None = None) -> dict:
    """{"ok": bool, "note": str} — sosem dob."""
    wd = _workdir(entry, home)
    if not wd.is_dir():
        return {"ok": False, "note": f"plugin: NEM települt — nincs meg az ágens repója ({wd}); az ágens enélkül is fut"}
    env = claude_auth.unit_env(entry, home)
    repo = parse(plugin_source).add_arg
    r = run([str(claude_bin), "plugin", "marketplace", "add", repo], env, cwd=wd)
    if not _ok(r):
        return {"ok": False, "note": f"plugin: NEM települt — {_why(r, repo)}; az ágens enélkül is fut"}
    r = run([str(claude_bin), "plugin", "install", PLUGIN_KEY, "--scope", "local"], env, cwd=wd)
    if not _ok(r):
        return {"ok": False, "note": f"plugin: NEM települt ({PLUGIN_KEY}) — {_why(r, repo)}; az ágens enélkül is fut"}
    try:
        old = _enable_local(wd)
    except (OSError, ValueError) as e:
        return {"ok": False, "note": f"plugin: {PLUGIN_KEY} telepítve, de a settings.local.json nem íródott "
                                     f"({type(e).__name__}); a régi fleet plugin bekapcsolva maradhatott"}
    off = f"; kikapcsolva: {', '.join(old)}" if old else ""
    return {"ok": True, "note": f"plugin: {PLUGIN_KEY} telepítve, local scope, {wd}{off}"}


def cmd_install(a) -> int:
    from fleet import registry as reg
    from fleet.install_checks import CLAUDE_BIN
    e = reg.get_agent(a.agent)
    if e is None:
        print(f"nincs ilyen ágens a registryben: {a.agent}", file=sys.stderr)
        return 2
    r = install_plugin(e, claude_bin=CLAUDE_BIN, home=Path.home(), plugin_source=a.plugin_source)
    print(r["note"])
    return 0 if r["ok"] else 1


def add_parser(sub) -> None:
    p = sub.add_parser("plugin", help="a /fleet:* plugin az ágens repójában (local scope)")
    ps = p.add_subparsers(dest="plugin_cmd", required=True)
    x = ps.add_parser("install", help="fleet@mentat --scope local az ágens repójában; a régi fleet@* ki")
    x.add_argument("agent")
    x.add_argument("--plugin-source", metavar="local:<út>")
    x.set_defaults(fn=cmd_install)
