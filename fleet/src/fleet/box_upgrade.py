"""`fleet box-upgrade --to <tag>` — a box egy parancsos, visszaállítható frissítése.

A lépések kis objektumok (terv → végrehajtás → ellenőrzés → visszaállítás); a
mag csak sorban hívja őket. Új lépés (plugin-váltás, motor-vendorolás) a
`default_steps()` listájába kerül, a mag változatlan. Előbb MINDEN lépés terve
kiíródik; `--dry-run` itt megáll, és semmit nem ír. Bukáskor a már lefutott
lépések fordított sorrendben visszaállnak — kivéve a `Halt`-ot (a kanári utáni
ágens bukása), ahol a már frissített rész marad. Nincs LLM-hívás; ahol a unit és
a híd nem változott, ott nincs újraindítás.
"""
from __future__ import annotations
import fcntl
import json
import sys
from dataclasses import dataclass, field
from typing import Callable

# Minden modul MOST töltődik be: a checkout a futó processz alatt cserélődik, egy
# később betöltött modul már az új kódból jönne (vegyes kód egy processzben).
from fleet import box_agents, box_checkout, box_snapshot
from fleet.box_signals import interruptible
from fleet.box_ctx import Ctx, Halt, StepFailed, PUBLIC_URL, private
from fleet.box_report import format_summary, write_receipt


@dataclass(frozen=True)
class Step:
    name: str
    plan: Callable[[Ctx], list[str]]
    apply: Callable[[Ctx], None]
    verify: Callable[[Ctx], None] = field(default=lambda ctx: None)
    rollback: Callable[[Ctx], list[str]] = field(default=lambda ctx: [])


def _mod(name: str, m) -> Step:
    return Step(name, m.plan, m.apply, getattr(m, "verify", lambda ctx: None), m.rollback)


def default_steps() -> list[Step]:
    return [_mod("pillanatkép", box_snapshot), _mod("checkout", box_checkout),
            _mod("ágensek", box_agents)]
    # TODO(docs/migration/boxes.md 6. lépés): plugin-váltás fleet@fleet-leader → fleet@mentat
    #   ágensenként (`fleet plugin install` + idle restart) — külön Step a lista végére.
    # TODO(boxes.md 7. lépés): motor-vendorolás (`engine/sync-to.sh`) — szintén külön Step.


def run(ctx: Ctx, steps: list[Step] | None = None, confirm: Callable[[], bool] | None = None) -> dict:
    steps = steps or default_steps()
    out = {"to": ctx.tag, "result": "", "error": None}
    try:
        lines = [ln for s in steps for ln in s.plan(ctx)]
    except (StepFailed, OSError) as e:
        out.update(result="failed-plan", error=str(e))
        ctx.say(f"TERV NEM KÉSZÜLT: {e} — semmihez nem nyúltam")
        return out
    ctx.say(f"fleet box-upgrade → {ctx.tag}" + (" (DRY RUN: semmit nem írok)" if ctx.dry_run else ""))
    for ln in lines:
        ctx.say(ln)
    if ctx.dry_run:
        out["result"] = "dry-run"
        return out
    if confirm is not None and not confirm():
        out["result"] = "aborted"
        return out
    lock_path = ctx.home / ".config" / "fleet" / "upgrades.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            out.update(result="failed-plan", error="már fut egy box-upgrade ezen a boxon")
            ctx.say(out["error"])
            return out
        with interruptible():
            _apply(ctx, steps, out)
        if ctx.state.get("rollback_errors"):   # a „visszaállítva" itt hazugság lenne
            out["result"] = "rollback-failed"
        with private():
            write_receipt(ctx, out, lines)
    ctx.say(format_summary(ctx, out))
    return out


def _apply(ctx: Ctx, steps: list[Step], out: dict) -> None:
    done: list[Step] = []
    try:
        for s in steps:
            ctx.say(f"== {s.name}")
            done.append(s)
            s.apply(ctx)
            s.verify(ctx)
        busy = any(a["result"] == "skipped-busy" for a in ctx.agents)
        out["result"] = "partial" if busy else "ok"
    except Halt as e:
        out.update(result="halted", error=str(e))
    except (Exception, KeyboardInterrupt) as e:   # noqa: BLE001 — minden bukás visszaállít…
        out["error"] = str(e) if isinstance(e, StepFailed) else f"{type(e).__name__}: {e}"
        if any(a["result"] == "ok" and a.get("did") for a in ctx.agents):
            out["result"] = "halted"   # …kivéve, ha már fut ágens az új kódon: azt nem rántjuk vissza
            return
        out["result"] = "rolled-back"
        for s in reversed(done):
            try:
                ctx.rolled_back += s.rollback(ctx)
            except (Exception, KeyboardInterrupt) as re:  # noqa: BLE001
                ctx.state.setdefault("rollback_errors", []).append(f"{s.name}: {re}")
                ctx.not_rolled_back.append(f"{s.name}: a visszaállítás bukott: {re}")


def _last_from_file(ctx: Ctx) -> list[str]:
    try:
        p = ctx.home / ".config" / "fleet" / "upgrade-last"
        return [ln.strip() for ln in p.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def cmd_box_upgrade(a) -> int:
    from pathlib import Path
    ctx = Ctx(home=Path.home(), tag=a.to, url=a.repo_url, dry_run=a.dry_run, canary=a.canary,
              only=a.only or [])
    ctx.last = (a.last or []) + [n for n in _last_from_file(ctx) if n not in (a.last or [])]

    def confirm() -> bool:
        if a.yes:
            return True
        if not sys.stdin.isatty():
            print("box-upgrade: nem interaktív futás — a végrehajtáshoz `--yes` kell (a terv fent)")
            return False
        return input("Indulhat? [i/N] ").strip().lower() in ("i", "igen", "y", "yes")
    r = run(ctx, confirm=confirm)
    if a.json:
        print(json.dumps({**r, "agents": ctx.agents}, ensure_ascii=False, indent=2))
    return {"ok": 0, "dry-run": 0, "partial": 3}.get(r["result"], 1)


def add_parser(sub) -> None:
    x = sub.add_parser("box-upgrade", help="EGY parancs: a box checkoutja a cél-tagre + ágensenként "
                       "install/híd kanárival, visszaállítással (0 kész · 3 részleges · 1 hiba)")
    x.add_argument("--to", required=True, metavar="TAG", help="cél-tag, pl. v0.5.1")
    x.add_argument("--dry-run", action="store_true", help="csak a terv; semmit nem ír")
    x.add_argument("--canary", metavar="ÁGENS", help="ez megy elsőnek (alapból: a sorrend első ágense)")
    x.add_argument("--only", action="append", metavar="ÁGENS", help="csak ezek az ágensek (ismételhető)")
    x.add_argument("--last", action="append", metavar="ÁGENS",
                   help="ezek a végére (ismételhető; a ~/.config/fleet/upgrade-last fájl is)")
    x.add_argument("--yes", action="store_true", help="kérdés nélkül végrehajt")
    x.add_argument("--repo-url", default=PUBLIC_URL, help=f"a kiadási repó (alap: {PUBLIC_URL})")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=cmd_box_upgrade)
