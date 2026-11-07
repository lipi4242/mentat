"""Egy ágens hídjának frissítése a box-upgrade-ben, visszaállítással.

A `fleet bridge rollback` a legújabb `sub-etha.bak-*`-ot hozza vissza, a unit-fájlt
nem. Ezért a telepítés előtt felírjuk, milyen mentések vannak és mi a unit
szövege; bukáskor:
  * ha ez a telepítés hozott létre új mentést → `bridge rollback` (az a miénk);
  * ha nem → a sub-etha/ érintetlen, a rollback egy RÉGEBBI mentést hozna vissza
    (visszalépés), ezért nem futtatjuk;
  * a unit-fájl mindkét esetben a felírt szövegre áll vissza.
A híd újraindítása a mérés szerint (#21) az ágenst is érintheti: dolgozó ágensnél
a box_agents ki sem hagyja ide.
"""
from __future__ import annotations

from fleet.box_agent_ops import postcheck
from fleet.box_ctx import Ctx, StepFailed, sh
from fleet.bridge_ops import _unit as bridge_unit

SETTLE_S = 5


def _baks(ctx: Ctx, agent: str) -> set[str]:
    return {p.name for p in (ctx.home / ".config" / agent).glob("sub-etha.bak-*")}


def snapshot(ctx: Ctx, e: dict) -> dict:
    unit = ctx.unit_dir / bridge_unit(e)
    return {"agent": e["agent"], "unit": bridge_unit(e), "baks": sorted(_baks(ctx, e["agent"])),
            "unit_text": unit.read_text() if unit.exists() else None}


def rollback(ctx: Ctx, snap: dict) -> str:
    agent, unit_path = snap["agent"], ctx.unit_dir / snap["unit"]
    notes = []
    cur = unit_path.read_text() if unit_path.exists() else None
    if cur != snap["unit_text"]:
        if snap["unit_text"] is None:
            unit_path.unlink()
        else:
            unit_path.write_text(snap["unit_text"])
        ctx.run(["systemctl", "--user", "daemon-reload"])
        notes.append("unit-fájl visszaírva")
    if _baks(ctx, agent) - set(snap["baks"]):
        back = ctx.run([str(ctx.new_fleet), "bridge", "rollback", agent])
        if back.returncode != 0:
            raise StepFailed(f"{agent}: a bridge rollback bukott (kód {back.returncode})")
        notes.append("sub-etha visszaállítva (bridge rollback)")
    else:   # nincs új mentés: a sub-etha nem mozdult; egy régi .bak visszahozása visszalépés lenne
        sh(ctx, ["systemctl", "--user", "restart", snap["unit"]], what=f"{snap['unit']} restart")
        notes.append("sub-etha érintetlen (nem volt új mentés), a híd újraindítva")
    return "; ".join(notes)


def upgrade(ctx: Ctx, e: dict) -> str:
    agent = e["agent"]
    snap = ctx.state["bridge_inflight"] = snapshot(ctx, e)   # a megszakítás is innen áll vissza
    try:
        sh(ctx, [ctx.new_fleet, "bridge", "install", agent], what=f"{agent}: bridge install")
        sh(ctx, ["systemctl", "--user", "restart", snap["unit"]], what=f"{snap['unit']} restart")
        ctx.sleep(SETTLE_S)   # egy azonnal elhaló node-processz is „active" a restart után
        state = ctx.run(["systemctl", "--user", "is-active", snap["unit"]]).stdout.strip()
        if state != "active":
            raise StepFailed(f"{snap['unit']} nem aktív a restart után ({state or 'nincs válasz'})")
        pc = postcheck(ctx, agent, 30)
    except StepFailed as err:
        ctx.state.pop("bridge_inflight", None)
        try:
            msg = rollback(ctx, snap)
        except (StepFailed, OSError) as re:
            ctx.state.setdefault("rollback_errors", []).append(f"{agent} híd: {re}")
            raise StepFailed(f"{err}; a híd visszaállítása IS bukott: {re}")
        raise StepFailed(f"{err}; a híd: {msg}")
    ctx.state.pop("bridge_inflight", None)
    return "bridge install + híd-újraindítás" + (" (függő postcheck)" if pc == "pending" else "")
