"""Ágensenként, sorban (runbook 4. lépés): zár → install, ha a unit/drop-in
változott → bridge install, ha drift van → postcheck → zár fel. Az első bukásnál
— BÁRMILYEN kivételnél, a Ctrl-C-t és a megszakadt ssh-t is beleértve — megáll:
  * ha még egy ágens sem frissült: StepFailed → a checkout is visszaáll, és a
    visszaállt kóddal újra települ minden „piszkos" ágens (box_checkout_undo);
  * ha már frissült valaki: Halt → a checkout és a frissítettek maradnak, a
    félbehagyott ágens az új kóddal települ újra (előre javítás).
A félbehagyott híd mindkét esetben visszaáll (box_bridge).
"""
from __future__ import annotations

from fleet import box_bridge, maintenance
from fleet.box_agent_ops import install
from fleet.box_agent_plan import analyze, busy, describe, ordered, supervision_stale
from fleet.box_ctx import Ctx, Halt, StepFailed

LOCK_TTL_MIN = 30


def plan(ctx: Ctx) -> list[str]:
    agents = ordered(ctx)
    ready = ctx.state.get("checkout_noop")   # a cél-kód már a helyén: most is mérhető
    lines = [f"ágensek ({len(agents)}), ebben a sorrendben:"]
    for i, e in enumerate(agents):
        a = analyze(ctx, e) if ready else None
        lines.append(f"  {i + 1}. {describe(a, e, busy_now=busy(ctx, e))}" + ("  ← kanári" if i == 0 else ""))
    if ready and supervision_stale(ctx):
        lines.append("  felügyeleti unitok a régi útra mutatnak → az első install átírja (restart nélkül)")
    return lines


def upgrade_agent(ctx: Ctx, e: dict, *, force_install: bool = False) -> dict:
    agent = e["agent"]
    a = analyze(ctx, e)
    res = {"agent": agent, "unit_changed": a["unit_changed"], "dropin_changed": a["dropin_changed"],
           "bridge_drift": a["bridge_drift"], "did": [], "result": "noop"}
    need_install = a["unit_changed"] or a["dropin_changed"] or force_install
    is_busy = busy(ctx, e)
    ctx.say(f"  terv (új kóddal): {describe(a, e, busy_now=is_busy)}")
    if not need_install and not a["bridge_drift"]:
        return res
    # a unit-csere és a hídcsere is újraindítja az ágenst (#21): dolgozót egyikkel sem
    if (a["unit_changed"] or a["bridge_drift"]) and is_busy:
        res["result"] = "skipped-busy"
        return res
    maintenance.lock(agent, LOCK_TTL_MIN)
    try:
        if need_install:
            res["did"].append(install(ctx, agent) + (" (újraindítva)" if a["unit_changed"] else ""))
        if a["bridge_drift"]:
            res["did"].append(box_bridge.upgrade(ctx, e))
    except StepFailed as err:
        res["result"], res["error"] = "failed", str(err)
        return res
    finally:
        maintenance.unlock(agent)
    res["result"] = "ok"
    return res


def _salvage(ctx: Ctx, agent: str, forward: bool) -> None:
    """Egy megszakított ágens rendbetétele: a félbehagyott híd vissza; a félbehagyott
    install előre (új kóddal, ha a checkout marad) — különben a checkout-visszaállítás
    telepíti újra a régi kóddal (a `dirty` listáról)."""
    st = ctx.state
    snap = st.pop("bridge_inflight", None)
    if snap:
        try:
            ctx.not_rolled_back.append(f"{agent} híd: {box_bridge.rollback(ctx, snap)}")
        except (Exception, KeyboardInterrupt) as e:  # noqa: BLE001
            st.setdefault("rollback_errors", []).append(f"{agent} híd: {e}")
    inflight = st.pop("install_inflight", None)
    if inflight and (forward or not st.get("switched")):   # nincs régi kód, amire visszaállhatnánk
        try:
            note = install(ctx, inflight)
            ctx.not_rolled_back.append(f"{inflight}: a megszakított install újra lefutott ({note})")
        except (Exception, KeyboardInterrupt) as e:  # noqa: BLE001
            st.setdefault("rollback_errors", []).append(f"{inflight}: újratelepítés: {e}")


def apply(ctx: Ctx) -> None:
    agents = ordered(ctx)
    stale = supervision_stale(ctx)
    for i, e in enumerate(agents):
        try:
            res = upgrade_agent(ctx, e, force_install=stale and i == 0)
        except (Exception, KeyboardInterrupt) as exc:   # noqa: BLE001 — render-hiba, Ctrl-C, SIGHUP…
            res = {"agent": e["agent"], "did": [], "result": "failed", "error": f"{type(exc).__name__}: {exc}"}
        if res["result"] == "ok" and any(d.startswith("install") for d in res["did"]):
            stale = False
        ctx.agents.append(res)
        ctx.say(f"  {e['agent']}: {res['result']}" + (f" ({', '.join(res['did'])})" if res["did"] else "")
                + (f" — {res['error']}" if res.get("error") else ""))
        if res["result"] != "failed":
            continue
        done = [r["agent"] for r in ctx.agents if r["result"] == "ok" and r["did"]]
        _salvage(ctx, e["agent"], forward=bool(done))
        rest = [x["agent"] for x in agents[i + 1:]]
        if done:
            ctx.not_rolled_back.append(f"frissítve marad: {', '.join(done)}")
        if rest:
            ctx.not_rolled_back.append(f"nem került sorra: {', '.join(rest)}")
        if not done:   # ez volt az első ténylegesen frissített ágens: a kanári
            raise StepFailed(f"a kanári ({e['agent']}) bukott: {res['error']}")
        raise Halt(f"{e['agent']} bukott: {res['error']}")


def rollback(ctx: Ctx) -> list[str]:
    """Az ágensek a saját tranzakciójukban, vagy a _salvage-ben már rendbe jöttek; a
    piszkos unitokat a checkout-visszaállítás telepíti újra a régi kóddal."""
    return []
