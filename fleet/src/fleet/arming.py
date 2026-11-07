"""Birth-time arming verification: did this agent's loop actually wind up?

WHY THIS IS NOT `liveness.should_rearm`
---------------------------------------
`liveness.should_rearm` answers the STEADY-STATE question — "this agent used to
tick and stopped" — and it deliberately returns False when `tick_age_s is None`,
because an unobservable tick trace (a misconfigured marker) would otherwise
re-arm forever and pile up duplicate crons.

That guard is right, and it is also exactly the hole a newborn falls through. A
freshly started agent has NEVER ticked: no `last-tick.json`, no marker in the
transcript, so `tick_age_s` is `None` — the one value the steady-state check
treats as "not stale". The agent sits alive and silent, its unit reports
`active`, and nothing is wrong anywhere a human would look.

Observed on 2026-08-12: an agent's first start rendered `ExecStartPost=/bin/sh -c
'sleep 10; tmux send-keys …'`, the send landed before the session was ready, the
loop was never armed, and the unit was `active` throughout. It only came up
because a human read the tmux pane.

WHY BOUNDED, AND WHY NOT IN ExecStartPost
------------------------------------------
The storm risk that justifies the steady-state guard is real, so this check is
BOUNDED: a fixed, small number of re-arm attempts inside a deadline derived from
the agent's own `tick_period_s`, then a loud failure. A bounded verifier cannot
storm; it can only give up and say so.

It also must not run as `ExecStartPost`. If ExecStartPost fails, systemd marks
the unit `failed` while the tmux session and the Claude process keep running —
a half-running state more confusing than the fault it reports. This is a
separate step (a CLI phase today, its own timer later), so failure is reported
without lying about the agent's process state.

THE SIGNAL
----------
"Armed" is not "the loop printed something". It is the agent's own tick landing
after the unit started, read from `last-tick.json` (written ONLY on scheduled
triggers — a human poke can never forge it) or the transcript marker, whichever
is fresher. Both are already implemented in `liveness.tick_age_s`; this module
adds only the birth-time question and the bound.
"""
from __future__ import annotations

#: Head start before the first tick can reasonably be expected: the session has
#: to boot, load its brain, and accept the injected loop command.
DEFAULT_GRACE_S = 180

#: How many times we re-send the loop command before declaring failure. Two is
#: enough to cover a lost keystroke and a slow boot; more would be a storm
#: wearing a small number as a disguise.
DEFAULT_MAX_ATTEMPTS = 2

ARMED = "armed"
WAIT = "wait"
REARM = "rearm"
FAILED = "failed"


def deadline_s(tick_period_s: float, grace_s: float = DEFAULT_GRACE_S) -> float:
    """How long a newborn may stay silent before we act.

    Derived from the agent's OWN period, never a flat number — the sibling
    modules say the same and for the same reason: a flat 45 minutes would nag an
    hourly agent every hour and let a daily agent rot for a day.
    """
    return grace_s + float(tick_period_s)


def arming_verdict(*, tick_age_s: float | None, unit_uptime_s: float,
                   attempts_used: int, tick_period_s: float,
                   grace_s: float = DEFAULT_GRACE_S,
                   max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> str:
    """Pure: `armed` | `wait` | `rearm` | `failed`.

    The armed test is `tick_age_s < unit_uptime_s` — the tick is younger than
    the unit is. Comparing two ages sidesteps clock parsing and timezone skew
    entirely, and it answers the question that matters: did a tick land AFTER
    this start, or are we looking at evidence left by the previous one? A
    stale `last-tick.json` from before a restart is exactly the trap this
    avoids, and it is the trap a naive "the file exists" check falls into.
    """
    if tick_age_s is not None and tick_age_s < unit_uptime_s:
        return ARMED
    if unit_uptime_s < deadline_s(tick_period_s, grace_s):
        return WAIT
    if attempts_used < max_attempts:
        return REARM
    return FAILED


# ── I/O ───────────────────────────────────────────────────────────────────

def unit_uptime_s(unit: str, *, run=None) -> float | None:
    """Seconds since the unit last entered `active`, or None if unknowable.

    Read from `ActiveEnterTimestampMonotonic` (microseconds since boot) against
    `/proc/uptime`, NOT from the human-readable `ActiveEnterTimestamp`: the
    monotonic pair needs no date parsing, no locale, and no timezone, and it
    cannot be skewed by a clock adjustment between the two reads — which is
    precisely the kind of rare, unreproducible wrongness we must not build a
    health check on. A never-started unit reports 0, which we treat as unknown.
    """
    import subprocess

    runner = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    try:
        r = runner(["systemctl", "--user", "show", "-p",
                    "ActiveEnterTimestampMonotonic", "--value", unit])
    except OSError:
        return None
    if r is None or getattr(r, "returncode", 1) != 0:
        return None
    try:
        started_us = int((r.stdout or "").strip())
    except ValueError:
        return None
    if started_us <= 0:
        return None
    try:
        with open("/proc/uptime") as f:
            now_s = float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return max(0.0, now_s - started_us / 1_000_000.0)


def verify(entry: dict, *, poll_s: float = 20.0, sleep=None,
           grace_s: float = DEFAULT_GRACE_S,
           max_attempts: int = DEFAULT_MAX_ATTEMPTS,
           uptime=None, tick_age=None, rearm=None, log=print) -> dict:
    """Block until this agent is proven armed, or fail loudly. Never stores state.

    Returns {"agent", "verdict", "attempts", "waited_s"}. `verdict` is ARMED or
    FAILED — WAIT and REARM are internal steps, never a result: "still waiting"
    as an answer is how an unarmed agent gets recorded as fine.

    Every collaborator is injectable so the loop is testable without systemd,
    tmux, or real time.
    """
    import time as _time

    from fleet.liveness import DEFAULT_TICK_PERIOD_S, read_session_id
    from fleet.liveness import send_loop_cmd as _send
    from fleet.liveness import tick_age_s as _tick_age

    sleep = sleep or _time.sleep
    uptime = uptime or (lambda: unit_uptime_s(entry.get("unit") or f"{entry.get('agent')}.service"))
    tick_age = tick_age or (lambda: _tick_age(entry, read_session_id(entry.get("agent", "")) or ""))
    rearm = rearm or (lambda: _send(entry.get("session", ""), entry.get("loop_cmd") or ""))

    agent = entry.get("agent", "?")
    period = float(entry.get("tick_period_s") or DEFAULT_TICK_PERIOD_S)
    attempts = 0
    waited = 0.0

    while True:
        up = uptime()
        if up is None:
            # No start time means no reference point for "after this start".
            # Reporting armed here would be a guess dressed as a check.
            return {"agent": agent, "verdict": FAILED, "attempts": attempts,
                    "waited_s": waited,
                    "detail": "unit start time unreadable — is the unit running?"}
        v = arming_verdict(tick_age_s=tick_age(), unit_uptime_s=up,
                           attempts_used=attempts, tick_period_s=period,
                           grace_s=grace_s, max_attempts=max_attempts)
        if v == ARMED:
            return {"agent": agent, "verdict": ARMED, "attempts": attempts,
                    "waited_s": waited}
        if v == FAILED:
            return {"agent": agent, "verdict": FAILED, "attempts": attempts,
                    "waited_s": waited,
                    "detail": f"no tick after {attempts} re-arm attempt(s)"}
        if v == REARM:
            if not entry.get("loop_cmd"):
                return {"agent": agent, "verdict": FAILED, "attempts": attempts,
                        "waited_s": waited,
                        "detail": "no loop_cmd in the registry — nothing to re-send"}
            attempts += 1
            ok = rearm()
            log(f"{agent}: nem ütött a deadline-ig — újraélesítés "
                f"{attempts}/{max_attempts}" + ("" if ok else " (send-keys hiba)"))
        sleep(poll_s)
        waited += poll_s
