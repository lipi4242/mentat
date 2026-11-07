"""A `fleet box-upgrade` nyugtája: egy JSON-sor futásonként a
`~/.config/fleet/upgrades.log`-ba, a részletek a futás könyvtárában
(`~/.config/fleet/upgrades/<idő>/`), és egy rövid emberi összefoglaló.
"""
from __future__ import annotations
import datetime
import json

from fleet.box_ctx import Ctx

HEAD = {"ok": "KÉSZ", "partial": "RÉSZBEN KÉSZ (dolgozó ágens kihagyva — futtasd újra később)",
        "halted": "MEGÁLLT (a korábbiak frissítve maradnak)",
        "rolled-back": "NEM SIKERÜLT — VISSZAÁLLÍTVA", "failed-plan": "NEM INDULT",
        "rollback-failed": "NEM SIKERÜLT, ÉS A VISSZAÁLLÍTÁS/HELYREÁLLÍTÁS RÉSZBEN BUKOTT — kézzel nézd meg"}


def record(ctx: Ctx, out: dict) -> dict:
    st = ctx.state
    return {"at": datetime.datetime.now().isoformat(timespec="seconds"), "to": ctx.tag,
            "from": st.get("prev_tag") or st.get("prev_sha"), "layout": st.get("layout"),
            "result": out["result"], "error": out.get("error"),
            "agents": [{"agent": a["agent"], "result": a["result"], "did": a.get("did", [])}
                       for a in ctx.agents],
            "rolled_back": ctx.rolled_back, "not_rolled_back": ctx.not_rolled_back,
            "rollback_errors": ctx.state.get("rollback_errors", []),
            "receipt": str(ctx.receipt_dir)}


def write_receipt(ctx: Ctx, out: dict, plan_lines: list[str]) -> None:
    rec = record(ctx, out)
    log = ctx.home / ".config" / "fleet" / "upgrades.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    d = ctx.receipt_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "plan.txt").write_text("\n".join(plan_lines) + "\n")
    (d / "result.json").write_text(json.dumps({**rec, "agents": ctx.agents}, ensure_ascii=False, indent=2) + "\n")


def format_summary(ctx: Ctx, out: dict) -> str:
    lines = [f"box-upgrade → {ctx.tag}: {HEAD.get(out['result'], out['result'])}"]
    if out.get("error"):
        lines.append(f"  ! {out['error']}")
    for a in ctx.agents:
        lines.append(f"  {a['agent']}: {a['result']}" + (f" ({', '.join(a['did'])})" if a.get("did") else ""))
    lines += [f"  visszaállítva: {n}" for n in ctx.rolled_back]
    lines += [f"  NEM állt vissza: {n}" for n in ctx.not_rolled_back]
    lines.append(f"  nyugta: {ctx.receipt_dir} · napló: ~/.config/fleet/upgrades.log")
    return "\n".join(lines)
