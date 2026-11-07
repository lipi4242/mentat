"""Az új checkout `fleet install` / `fleet postcheck` hívása, a kimenet szerződésével.

Szerződés (a valódi CLI-n tesztelve: test_box_upgrade_contract):
  * `fleet install` kódja: 0 kész · 3 fut, a postcheck még nem dőlt el · más: bukott,
    és a saját tranzakciójában visszaállt. Jelzéssel megölt (negatív kód) install
    NEM áll vissza — az ágens „piszkos" marad, a box-upgrade állítja helyre.
  * `fleet postcheck` első sora: `postcheck <ágens>: OK|PENDING|FAILED (…)`.
"""
from __future__ import annotations

from fleet.box_ctx import Ctx, StepFailed


def postcheck(ctx: Ctx, agent: str, wait: int) -> str:
    """ok / pending; csak a FAILED bukás. Restart-idő nélkül a `fleet postcheck` a
    függő jelre (friss-e már a csatorna, landolt-e tick) is nem-nullát ad — az
    nem hiba, azt a reconcile viszi tovább, mint a `fleet install` függő ágát."""
    r = ctx.run([str(ctx.new_fleet), "postcheck", agent, "--wait", str(wait)])
    head = ((r.stdout or "").strip().splitlines() or [""])[0]
    if r.returncode == 0:
        return "ok"
    if ": PENDING" in head:
        return "pending"
    tail = " | ".join((r.stdout or "").strip().splitlines()[1:5])
    raise StepFailed(f"{agent}: postcheck → {head or f'kód {r.returncode}'}" + (f": {tail}" if tail else ""))


def install(ctx: Ctx, agent: str, fleet=None) -> str:
    """Az ágens a hívás ELŐTT kerül a `dirty` listára; csak tiszta (önmagát
    visszaállító) bukásnál jön le róla."""
    dirty = ctx.state.setdefault("dirty", [])
    dirty.append(agent)
    ctx.state["install_inflight"] = agent
    r = ctx.run([str(fleet or ctx.new_fleet), "install", agent])
    ctx.state.pop("install_inflight", None)
    if r.returncode == 3:     # fut, stabil, a postcheck még nem dőlt el: a reconcile viszi
        return "install (függő postcheck — a reconcile viszi tovább)"
    if r.returncode == 0:
        return "install"
    tail = " | ".join((r.stdout or "").strip().splitlines()[-5:])
    if r.returncode > 0:      # a fleet install a saját tranzakciójában visszaállt
        dirty.remove(agent)
        raise StepFailed(f"{agent}: fleet install → kód {r.returncode} (a unitot a fleet install "
                         f"visszaállította): {tail}")
    raise StepFailed(f"{agent}: fleet install jelzéssel leállt (kód {r.returncode}) — "
                     f"NEM állt vissza magától: {tail}")
