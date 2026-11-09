"""`fleet tick-gate run <ágens>` — a timer egy tüzelése. LLM nélkül.

1. nyom: `fired_at` (mindig — a flotta-check ebből látja, hogy a timer él);
2. karbantartási zár alatt, vagy ha még nem esedékes (tétlen mód): kilép, HTTP nélkül;
3. előellenőrzés (`builtin:release` vagy argv-parancs) → tick_gate_decide;
4. beküldés csak `inject`-nél, és csak ha az ágens nem foglalt; a bukott beküldés `busy`.
A nyom (`<workdir>/data/state/tick-gate.json`) atomikus (tmp + rename).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from fleet import liveness, maintenance
from fleet import tick_gate as tg
from fleet import tick_gate_decide as dec
from fleet import tick_gate_inject as inj

TRACE = "tick-gate.json"


def trace_path(entry: dict, home: Path) -> Path:
    return liveness.state_path(str(entry["workdir"]).replace("%h", str(home)), TRACE)


def load(p: Path) -> dict:
    try:
        d = json.loads(p.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tick-gate-", dir=p.parent)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def last_tick_at(entry: dict, gate: dict, home: Path) -> float | None:
    """Az utolsó tick: a kapu beküldése vagy az ágens saját last-tick.json-ja, a frissebb."""
    vals = [gate.get("injected_at")]
    try:
        vals.append(trace_path(entry, home).with_name("last-tick.json").stat().st_mtime)
    except OSError:
        pass
    real = [float(v) for v in vals if isinstance(v, (int, float)) and v]   # romlott nyom: figyelmen kívül
    return max(real) if real else None


def observe_cmd(argv: list[str], run=subprocess.run) -> dict:
    """Saját előellenőrző: stdout `{"work": bool, "activity"?: bool, "reasons"?: [...]}`."""
    try:
        r = run(argv, capture_output=True, text=True, timeout=5)
        d = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {"activity": False, "reasons": [], "error": f"előellenőrző: {type(e).__name__}", "commit": {}}
    if not isinstance(d, dict) or not isinstance(d.get("reasons", []), list):
        return {"activity": False, "reasons": [], "error": f"előellenőrző: kód {r.returncode} / hibás alak", "commit": {}}
    reasons = [str(x)[:200] for x in d.get("reasons") or []] or (["előellenőrző: munka"] if d.get("work") else [])
    return {"activity": bool(d.get("activity", d.get("work"))), "reasons": reasons if d.get("work") else [],
            "error": None, "commit": {}}


def transcript_mtime(entry: dict) -> float | None:
    sid = liveness.read_session_id(entry["agent"])
    age = liveness.transcript_age_s(sid, time.time()) if sid else None
    return None if age is None else time.time() - age


def busy_reason(entry: dict, now: float, capture=None) -> str | None:
    sid = liveness.read_session_id(entry["agent"])
    why = inj.transcript_busy(liveness.transcript_age_s(sid, now) if sid else None, liveness.TRANSCRIPT_FRESH_S)
    if why:
        return why
    from fleet import pane
    return inj.pane_busy((capture or pane.capture)(entry["session"]))


def run_once(entry: dict, *, home: Path | None = None, now: float | None = None, observe=None,
             busy=busy_reason, send=inj.send) -> dict:
    home = home or Path.home()
    now = time.time() if now is None else now
    cfg = tg.config(entry)
    if cfg is None:
        return {"action": "none", "why": ["nincs tick_gate a registryben"]}
    p = trace_path(entry, home)
    gate = load(p)
    gate["fired_at"] = now
    if maintenance.is_locked(entry["agent"]) or not tg.due(gate, now):
        why = "karbantartási zár" if maintenance.is_locked(entry["agent"]) else "még nem esedékes (tétlen mód)"
        gate["skipped"] = why
        save(p, gate)
        return {"action": "skip", "why": [why]}
    gate.pop("skipped", None)
    gate, lost = dec.settle_ack(gate, transcript_mtime(entry), now)
    lt = last_tick_at(entry, gate, home)
    if observe is None:
        if isinstance(cfg["check"], list):
            obs = observe_cmd(cfg["check"])
        else:
            from fleet.precheck_release import observe as rel
            obs = rel(cfg, gate, now=now, last_tick_at=lt, home=home)
    else:
        obs = observe(cfg, gate, now=now, last_tick_at=lt, home=home)
    if lost:
        obs = {**obs, "reasons": [lost, *obs.get("reasons", [])]}
    res = dec.decide(cfg, gate, obs, now=now, last_tick_at=lt, busy=None)
    if res["action"] == "inject":
        why = busy(entry, now)
        if why:
            res = dec.deferred(res, gate, cfg, why, now)
        else:
            ok, msg = send(entry["session"], cfg["tick_cmd"])
            res = res if ok else dec.deferred(res, gate, cfg, msg, now)
    res["state"]["elapsed_ms"] = int((time.time() - now) * 1000) if now <= time.time() else None
    save(p, res["state"])
    return {k: v for k, v in res.items() if k != "state"}
