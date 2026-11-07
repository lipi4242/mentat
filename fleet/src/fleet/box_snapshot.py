"""Pillanatkép a csere előtt (runbook 1. lépés), a nyugta-könyvtárba:
előző sha/tag, `fleet doctor` a RÉGI kóddal, a `fleet-leader`-re hivatkozó
fájlok listája, és amit a reconcile már előtte is tenne (ehhez méri magát az
ellenőrzés: ami előtte is piros volt, azt nem a csere rontotta el).
"""
from __future__ import annotations
import json

from fleet.box_checkout import would_act
from fleet.box_ctx import Ctx, SLOW_TIMEOUT_S, private


def old_fleet(ctx: Ctx):
    return ctx.link / "bin" / "fleet"


def plan(ctx: Ctx) -> list[str]:
    return [f"pillanatkép + nyugta: {ctx.receipt_dir}"]


def refs(ctx: Ctx) -> list[str]:
    """Fájlok, amik még a `fleet-leader` útra hivatkoznak (a `.bak-*` mentések nélkül)."""
    files = [p for p in ctx.unit_dir.rglob("*") if p.is_file() and ".bak-" not in p.name] \
        if ctx.unit_dir.is_dir() else []
    files += sorted(ctx.home.glob(".claude*/settings.json"))
    out = []
    for p in files:
        try:
            if "fleet-leader" in p.read_text(errors="replace"):
                out.append(str(p))
        except OSError:
            pass
    return sorted(out)


def apply(ctx: Ctx) -> None:
    with private():
        _write(ctx)


def _write(ctx: Ctx) -> None:
    d = ctx.receipt_dir
    d.mkdir(parents=True, exist_ok=True)
    st = ctx.state
    pre = {k: st.get(k) for k in ("layout", "prev_sha", "prev_tag", "target_sha")}
    (d / "pre-state.json").write_text(json.dumps({**pre, "to": ctx.tag}, indent=2) + "\n")
    doc = ctx.run_t([str(old_fleet(ctx)), "doctor"], SLOW_TIMEOUT_S)
    (d / "doctor.pre.txt").write_text((doc.stdout or "") + (doc.stderr or ""))
    (d / "fleet-leader-refs.pre.txt").write_text("".join(f"{r}\n" for r in refs(ctx)))
    obs = ctx.run_t([str(old_fleet(ctx)), "reconcile", "--observe"], SLOW_TIMEOUT_S)
    (d / "observe.pre.txt").write_text(obs.stdout or "")
    st["observe_before"] = sorted(would_act(obs.stdout or ""))


def verify(ctx: Ctx) -> None:
    pass


def rollback(ctx: Ctx) -> list[str]:
    return []     # a nyugta megmarad: abból látszik, mi történt
