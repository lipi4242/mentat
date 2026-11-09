"""CLI: `fleet tick-gate presets|render|install|run|status`, `fleet precheck release`, `fleet wake`."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def _entry(name: str) -> dict:
    from fleet import registry as reg
    e = reg.get_agent(name)
    if e is None:
        print(f"nincs ilyen ágens a registryben: {name}", file=sys.stderr)
        raise SystemExit(2)
    return e


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def cmd_presets(_a) -> int:
    from fleet import tick_gate as tg
    print(tg.QUESTION)
    _out({k: v for k, v in tg.PRESETS.items()})
    return 0


def cmd_render(a) -> int:
    from fleet.install import fleet_root_for_units
    from fleet.tick_gate_units import render
    files = render(_entry(a.agent), fleet_root_for_units())
    for name, text in files.items():
        print(f"# --- {name}\n{text}")
    return 0 if files else 1


def cmd_install(a) -> int:
    from fleet.install import UNIT_DIR, fleet_root_for_units
    from fleet.tick_gate_units import install
    from fleet.txn import Txn, StepFailed
    t = Txn()
    try:
        notes = install(t, _entry(a.agent), UNIT_DIR, fleet_root_for_units())
    except (StepFailed, OSError, ValueError) as e:
        print(f"tick-kapu telepítés HIBA: {e}", file=sys.stderr)
        for n in t.rollback():
            print(n, file=sys.stderr)
        return 1
    print("\n".join(notes) or "tick-kapu: nincs változás (vagy nincs tick_gate a registryben)")
    return 0


def cmd_run(a) -> int:
    from fleet.tick_gate_run import run_once
    _out(run_once(_entry(a.agent)))
    return 0   # a döntés a nyomban él; a timer unitja ne menjen `failed`-be egy üres kör miatt


def cmd_status(a) -> int:
    from fleet.tick_gate_health import verdict
    from fleet.tick_gate_run import load, trace_path
    e = _entry(a.agent)
    v = verdict(e)
    g = load(trace_path(e, Path.home()))
    _out({**v, "reasons": g.get("reasons"), "error": g.get("error"), "elapsed_ms": g.get("elapsed_ms"),
          "day_count": g.get("day_count")})
    return 0 if v["state"] in ("ok", "pending", "n/a") else 1


def cmd_precheck(a) -> int:
    """Száraz futás: a döntés, beküldés és nyom-írás nélkül (asztalon is)."""
    from fleet import tick_gate as tg
    from fleet.precheck_release import observe
    from fleet.tick_gate_run import last_tick_at, load, trace_path
    e = _entry(a.agent)
    cfg = tg.config(e)
    if cfg is None:
        print("nincs tick_gate a registryben", file=sys.stderr)
        return 2
    gate = load(trace_path(e, Path.home()))
    t0 = time.time()
    obs = observe(cfg, gate, now=t0, last_tick_at=last_tick_at(e, gate, Path.home()), home=Path.home())
    obs.pop("commit", None)
    _out({**obs, "work": bool(obs["reasons"]), "elapsed_ms": int((time.time() - t0) * 1000)})
    return 0


def cmd_wake(a) -> int:
    from fleet.wake import wake
    code, out = wake(_entry(a.agent), a.reason, a.pr)
    _out(out)
    if out.get("fallback"):
        print(f"\nTARTALÉK ({out['fallback']['why']}): küldd el peer-üzenetként:\n{out['fallback']['send']}")
    return code


def add_parser(sub) -> None:
    g = sub.add_parser("tick-gate", help="tick-kapu: LLM nélküli előellenőrzés, csak munka esetén tick")
    gs = g.add_subparsers(dest="sub", required=True)
    gs.add_parser("presets", help="a bekötés kadencia-kérdése és a három preset").set_defaults(fn=cmd_presets)
    for name, fn, h in (("render", cmd_render, "a kapu unitjai a registryből"),
                        ("install", cmd_install, "a kapu timerének telepítése és élesítése"),
                        ("run", cmd_run, "egy tüzelés (a timer ExecStart-ja)"),
                        ("status", cmd_status, "a nyom ítélete (ok/pending/red) + az utolsó döntés")):
        x = gs.add_parser(name, help=h); x.add_argument("agent"); x.set_defaults(fn=fn)
    p = sub.add_parser("precheck", help="előellenőrzők száraz futása"); ps = p.add_subparsers(dest="sub", required=True)
    x = ps.add_parser("release", help="a kiadó ágens előellenőrzése (nem küld be, nem ír nyomot)")
    x.add_argument("--agent", required=True); x.set_defaults(fn=cmd_precheck)
    x = sub.add_parser("wake", help="ágens ébresztése: todo-feladat a principaljára; tartalék: peer-üzenet szövege")
    x.add_argument("agent"); x.add_argument("--reason", required=True); x.add_argument("--pr", help="a PR linkje")
    x.set_defaults(fn=cmd_wake)
