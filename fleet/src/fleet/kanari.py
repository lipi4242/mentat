"""11-07: felhasználói szintű Claude-beállítás írása kanárival — EGY közös segéd minden írónak.

    guarded(what, roots, write, home=…, agents=None, force=False) -> [jegyzet]
    record(home, roots, what)                  a gyökér mostani lenyomata = egy rögzített kanári-futás
    drift(home) -> [figyelmeztetés]            a doctor box-sora: változott-e rögzítés nélkül
    cmd_record(a)                              `fleet canary record` — kézi változás után

A box minden ágense egy (vagy néhány) Claude-gyökeret oszt (~/.claude, ~/.claude-<fiók>), és a
Claude Code a settings-hookokat azonnal újraolvassa: ami beíródik, az MINDEN futó sessionben él.
11-07-én egy ilyen írás (a titok-kapu) három ágenst némított el. Ezért minden író:

  1. kanári: az első olyan gyökér, amelyen ágens fut; előtte és utána az ágensei alapfunkció-
     próbája (essentials.py + kepesseg.py). Ha az írás ÚJ piros sort hoz, a gyökér visszaáll a
     pillanatképből (settings.json, plugins/*.json, skills/ új linkjei), és a többi érintetlen;
  2. csak ezután a többi gyökér;
  3. a megírt gyökerek lenyomata (hookok, enabledPlugins, telepített pluginok, skills) lemezre kerül.
A már az írás ELŐTT is piros ágens nem akasztja meg az írást (az nem ennek a változásnak a hibája).
Írók: claude_firstrun (SessionStart hook), operator_skills (skills/ link), plugin_install
(`claude plugin …`), titok_kanari (saját kanárija van; a lenyomatot ide rögzíti).
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

SNAP = ("settings.json", "plugins/installed_plugins.json", "plugins/known_marketplaces.json")
VOLATILE = ("installedAt", "lastUpdated")


class Refused(RuntimeError):
    pass


def state_path(home: Path) -> Path:
    return home / ".config" / "fleet" / "state" / "kanari.json"


def root_of(entry: dict, home: Path) -> Path:
    acc = entry.get("claude_account") or "shared"
    return home / ".claude" if acc == "shared" else home / f".claude-{acc}"


def _json(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in VOLATILE}
    return [_strip(v) for v in x] if isinstance(x, list) else x


def fingerprint(root: Path) -> str:
    s = _json(root / "settings.json")
    s = s if isinstance(s, dict) else {}
    plugins = _json(root / "plugins" / "installed_plugins.json")
    skills = sorted((p.name, os.readlink(p) if p.is_symlink() else "helyi") for p in (root / "skills").glob("*")) \
        if (root / "skills").is_dir() else []
    doc = [s.get("hooks"), s.get("enabledPlugins"), _strip((plugins or {}).get("plugins")) if isinstance(plugins, dict)
           else None, skills]
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _snapshot(root: Path) -> dict:
    files = {rel: (root / rel).read_bytes() if (root / rel).is_file() else None for rel in SNAP}
    skills = {p.name for p in (root / "skills").glob("*")} if (root / "skills").is_dir() else set()
    return {"files": files, "skills": skills}


def _restore(root: Path, snap: dict) -> None:
    for rel, data in snap["files"].items():
        p = root / rel
        if data is None:
            p.unlink(missing_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    for p in (root / "skills").glob("*") if (root / "skills").is_dir() else []:
        if p.name not in snap["skills"] and p.is_symlink():  # csak a mi új linkjeinket
            p.unlink()


def record(home: Path, roots: list[Path], what: str) -> None:
    p = state_path(home)
    st = _json(p) if p.is_file() else {}
    st = st if isinstance(st, dict) else {}
    for r in roots:
        st[str(r)] = {"fp": fingerprint(r), "at": time.time(), "what": what}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def probe(agents: list[dict], home: Path) -> dict[str, set[str]]:
    """Az ágensek piros sorai: kapu-döntés + token-előfeltétel + ténylegesen lefutó alapfunkciók."""
    from fleet import essentials, kepesseg, titok_telepit
    live = (titok_telepit.code_dir(home) / "current" / "titok_kapu.py").is_file()
    res = essentials.probe(agents, home, gate=live)
    by = {e["agent"]: e for e in agents}
    return {a: set(r["red"]) | set(kepesseg.check(by[a], home)["red"]) for a, r in res.items()}


def _local_agents() -> list[dict]:
    from fleet import essentials
    return essentials.local_agents()


def guarded(what: str, roots: list[Path], write, *, home: Path, agents: list[dict] | None = None,
            force: bool = False, probe_fn=None) -> list[str]:
    """`write(root) -> [jegyzet]` gyökerenként. Új piros a kanárin → visszaállítás + Refused."""
    agents, probe_fn = _local_agents() if agents is None else agents, probe_fn or probe
    on = {r: [e for e in agents if root_of(e, home) == r] for r in roots}
    order = sorted(roots, key=lambda r: not on[r])  # a kanári egy gyökér, amin ágens fut
    canary, notes = order[0] if order else None, []
    if canary is not None:
        before = probe_fn(on[canary], home) if on[canary] else {}
        snap = _snapshot(canary)
        notes += write(canary) or []
        after = probe_fn(on[canary], home) if on[canary] else {}
        new = {a: sorted(after[a] - before.get(a, set())) for a in after if after[a] - before.get(a, set())}
        if new:
            lines = "\n".join(f"   ! {a}: {x}" for a, xs in sorted(new.items()) for x in xs)
            if not force:
                _restore(canary, snap)
                raise Refused(f"{what}: a kanári ({canary}) után új alapfunkció-hiba — visszaállítva, "
                              f"a többi gyökér érintetlen:\n{lines}")
            notes.append(f"!!! --force: {what} ezekkel a hibákkal ment ki ({canary}):\n{lines}")
        notes.append(f"kanári: {canary.name} — " + (f"{len(on[canary])} ágens próbálva" if on[canary]
                                                    else "nincs rajta ágens, próba nélkül"))
    for r in order[1:]:
        notes += write(r) or []
    record(home, order, what)
    return notes


def drift(home: Path) -> list[str]:
    from fleet import titok_telepit
    p = state_path(home)
    st = (_json(p) if p.is_file() else None) or {}
    out = []
    for r in titok_telepit.roots(home):
        if not (r / "settings.json").is_file():
            continue
        rec = st.get(str(r)) if isinstance(st, dict) else None
        label = "~/" + r.name
        if not rec:
            out.append(f"{label}: nincs rögzített kanári-futás a felhasználói hookokra/pluginokra — "
                       "`fleet canary record` (próba + rögzítés)")
        elif rec.get("fp") != fingerprint(r):
            when = time.strftime("%m-%d %H:%M", time.localtime(rec.get("at", 0)))
            out.append(f"{label}: a felhasználói hookok/pluginok/skillek változtak rögzített kanári-futás nélkül "
                       f"(utolsó: {when}, {rec.get('what')}) — minden ágens ezen a gyökéren azonnal kapta; "
                       "`fleet canary record` (próba + rögzítés)")
    return out


def cmd_record(a) -> int:
    from fleet import titok_telepit
    home, agents, bad = Path.home(), _local_agents(), []
    roots = [r for r in titok_telepit.roots(home) if (r / "settings.json").is_file()]
    for r in roots:
        on = [e for e in agents if root_of(e, home) == r]
        red = {x: sorted(v) for x, v in probe(on, home).items() if v} if on else {}
        print(f"{'❌' if red else '✅'} ~/{r.name} ({len(on)} ágens)")
        for ag, xs in sorted(red.items()):
            print("".join(f"   ! {ag}: {x}\n" for x in xs), end="")
        bad += [r] if red else []
    ok = [r for r in roots if a.force or r not in bad]
    record(home, ok, "kézi rögzítés" + (" (--force)" if a.force and bad else ""))
    print(f"rögzítve: {len(ok)} gyökér" + (f"; NEM rögzítve (piros): {len(bad)}" if bad and not a.force else ""))
    return 1 if bad and not a.force else 0
