"""Ágensenként: mi változna a cél-kóddal, és milyen sorrendben menjünk.

A döntés az ÚJ checkouton mér: a unitot az új `fleet render` adja, a drop-int
az új sablon, a híd-driftet az új `bridge/` könyvtár. Amíg az új kód nincs a
helyén (a váltás előtti terv), ezek a mezők None-ok: „a váltás után mérve".
"""
from __future__ import annotations

from fleet.box_ctx import Ctx, BUSY_S, StepFailed, sh
from fleet.bridge_ops import drift_files
from fleet.registry import agents_for_host, is_dormant, load_agents, local_host


def host_agents(ctx: Ctx) -> list[dict]:
    if "registry_agents" in ctx.state:          # teszt / hívó által adott lista
        return ctx.state["registry_agents"]
    host = local_host()
    if host is None:   # különben 0 ágenssel is lefutna a checkout-csere
        raise StepFailed("ez a gép nincs a boxes.json-ban (és nincs FLEET_HOST) — nem tudom, mely ágensek ezek")
    return agents_for_host(host, load_agents())


def ordered(ctx: Ctx) -> list[dict]:
    """Kanári elöl; utána a nem proaktívak, aztán a proaktívak; a `last` lista a
    végén, a megadott sorrendben. `--only` szűr; ismeretlen név hiba."""
    agents = host_agents(ctx)
    names = {e["agent"] for e in agents}
    for n in ctx.only + ([ctx.canary] if ctx.canary else []):
        if n not in names:
            raise StepFailed(f"nincs ilyen ágens ezen a boxon: {n}")
    if ctx.only:
        agents = [e for e in agents if e["agent"] in ctx.only]
        if ctx.canary and ctx.canary not in ctx.only:
            raise StepFailed(f"a kanári ({ctx.canary}) nincs az --only listában")
    else:   # egy dormant ágenst nem indítunk, és a unitja sem sürgős: csak --only-val
        agents = [e for e in agents if not is_dormant(e) or e["agent"] == ctx.canary]
    last = [n for n in ctx.last if n in names]

    def key(e):
        a = e["agent"]
        return (a != ctx.canary, last.index(a) + 1 if a in last else 0, bool(e.get("proactive")), a)
    return sorted(agents, key=key)


def root_for_units(ctx: Ctx) -> str:
    """A cél-checkout útja, ahogy a unitok látják (install.fleet_root_for_units)."""
    return "%h/" + str((ctx.src / "fleet").relative_to(ctx.home))


def transcript_age(ctx: Ctx, e: dict) -> float | None:
    try:
        sid = (ctx.home / ".config" / e["agent"] / "session.id").read_text().strip()
    except OSError:
        return None
    acc = e.get("claude_account") or "shared"
    base = ctx.home / (".claude" if acc == "shared" else f".claude-{acc}")
    hits = sorted(base.glob(f"projects/*/{sid}.jsonl")) if sid else []
    try:
        return ctx.now() - hits[0].stat().st_mtime if hits else None
    except OSError:
        return None


def busy(ctx: Ctx, e: dict) -> bool:
    age = transcript_age(ctx, e)
    return age is not None and age < BUSY_S


def bridge_dir(ctx: Ctx, e: dict):
    return ctx.home / ".config" / e["agent"] / "sub-etha"


def analyze(ctx: Ctx, e: dict) -> dict:
    """Az ÚJ kóddal mér (a `ctx.src` már a cél-tagen áll)."""
    a, unit = e["agent"], e["unit"]
    out = {"agent": a, "proactive": bool(e.get("proactive")), "busy": busy(ctx, e)}
    installed = ctx.unit_dir / unit
    rendered = sh(ctx, [ctx.new_fleet, "render", a], what=f"{a}: új fleet render")
    out["unit_changed"] = not installed.exists() or installed.read_text() != rendered
    tmpl = ctx.src / "fleet" / "templates" / "10-session-gate.conf.tmpl"
    want = tmpl.read_text().replace("@@AGENT@@", a).replace("@@FLEET_ROOT@@", root_for_units(ctx)) \
        if tmpl.exists() else None
    dropin = ctx.unit_dir / f"{unit}.d" / "10-session-gate.conf"
    out["dropin_changed"] = want is not None and (not dropin.exists() or dropin.read_text() != want)
    d, custom = bridge_dir(ctx, e), (e.get("bridge") or {}).get("custom")
    # csak a MÁR telepített hidat frissítjük; újat nem húzunk fel, egyedit nem írunk felül
    out["bridge_drift"] = bool(d.is_dir() and not custom and drift_files(d, ctx.src / "fleet" / "bridge"))
    return out


def supervision_stale(ctx: Ctx) -> bool:
    """A felügyeleti unitok még nem a cél-checkoutra mutatnak — ezt az első
    `fleet install` írja át (ensure_supervision), restart nélkül."""
    root = root_for_units(ctx)
    files = [ctx.unit_dir / n for n in ("fleet-reconcile.service", "fleet-reconcile-fast.service")]
    return any(f.exists() and root not in f.read_text() for f in files)


def describe(a: dict | None, e: dict, *, busy_now: bool) -> str:
    tags = ["proaktív" if e.get("proactive") else "nem proaktív"] + (["DOLGOZIK"] if busy_now else [])
    if a is None:
        return f"{e['agent']} ({', '.join(tags)}): unit/híd a váltás után, az új kóddal mérve"
    skip = " — KIHAGYVA, dolgozik" if busy_now else ""
    todo = ([f"unit változik → install + újraindítás{skip}"] if a["unit_changed"] else []) + \
           (["drop-in változik → install (újraindítás nélkül)"] if a["dropin_changed"] and not a["unit_changed"] else []) + \
           ([f"híd-drift → bridge install + híd-újraindítás (az ágens is újraindulhat, #21){skip}"]
            if a["bridge_drift"] else [])
    return f"{e['agent']} ({', '.join(tags)}): " + ("; ".join(todo) or "nincs teendő")
