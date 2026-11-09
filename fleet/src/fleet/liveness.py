"""Liveness primitives: OOM protection + tick guard, used by the reconcile.

This used to be a SECOND controller on its own
3-minute timer, and it wrote the engine's heartbeat itself ("vouching") — two
writers, one reader. Now the reconcile is the one controller: it calls
`oom_sweep()` every round and decides re-arms with `should_rearm()`; NOTHING in
the fleet writes the heartbeat (only the engine does). Job 1 below is history,
kept because it explains why the transcript age is the liveness signal that the
reconcile reads directly (`signals.measure`).

Three jobs, all driven by `deploy/agents.json` so a new agent gets them free.

**1. Transcript heartbeat.** `entry.py` refreshes the heartbeat at the START of a
tick. During a LONG piece of work the /loop is busy, no tick runs, and after
`staleness_min` the supervisor would kill an agent that is working perfectly
well — an observed restart spiral in production. (That supervisor was the old
watchdog, with a 90-minute floor; it was removed (11-08), and the reconcile
now judges staleness from the agent's own `tick_period_s` × `TICK_STALE_FACTOR`
in `signals.schedule_verdict`.) The honest liveness signal is whether the
session is writing to its transcript: a working agent writes continuously.

The freshness window matters in both directions. Too long and we vouch for a
hung session; too short and a genuinely busy agent still gets killed. 10 minutes
is well inside the tick-derived staleness threshold of the default 30-minute
period (45 minutes); only a period under 400 s has a shorter threshold.

**2. OOM protection.** The box has 3.8G shared by 5+ Claude agents plus
CI-weight gate builds. Measured 2026-08-03: most agent processes sat at
`oom_score_adj=200` — MORE likely to be killed than an average process. On a
box whose whole purpose is those agents, the orchestrator was a preferred
victim over a throwaway build. Agents go to -600; builds stay as they are and
remain the preferred victims, which is the correct order.

The adjustment is per-PID, so it must be re-applied on every run — a restarted
agent is a new PID with the default value back.

**3. Tick guard.** A `/loop` timer is a `CronCreate` job that **auto-expires
after 7 days** — the tool says so in its own response. In one observed
case a job fired its last tick exactly on the seventh day and the agent then
stood silent for 38 hours, until a human wrote to it.

Job 1 could not catch that, and the reason matters more than the fix: the
heartbeat answers *"is this process alive"*, and the process was alive — it just
had no timer wound up. One signal cannot answer two questions. So the guard asks
the second question from a separate source (`last-tick.json`, or the tick's
trace in the transcript) and, when an **idle** agent has stopped ticking,
re-sends its `loop_cmd`. Idle-only, so it never types into a running release.

Every threshold here is derived from the agent's own `tick_period_s`, never a
flat number of minutes — see `should_rearm`.

This replaces per-agent shell copies of a liveness script, which drifted
independently.
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path


#: How stale a transcript may be and still count as "this agent is alive".
#: Well inside the tick-derived staleness threshold of the default period
#: (`signals.schedule_verdict`: period × TICK_STALE_FACTOR = 45 min at 1800 s).
TRANSCRIPT_FRESH_S = 600

#: Linux OOM adjustment for an agent process. Negative = protect.
AGENT_OOM_ADJ = -600

#: Validáló segédprogram a negatív oom_score_adj írásához. Lásd write_oom_adj.
OOM_HELPER = "/usr/local/sbin/oom-protect"

#: A tick-periodus, ha a registry nem mondja. A harom kiadasi agens 30 perces.
DEFAULT_TICK_PERIOD_S = 1800

#: A kuszobok a PERIODUSBOL szarmaznak, nem fix percekbol. Ez nem eleganciabol
#: van: a fix 45 perc egy oránként tickelő ágenst minden orában elavultnak
#: latta volna, es ora(!)ra ujrahuztuk volna egy tokeletesen egeszseges agenst.
#: A hibat a telepites elotti, boxon futtatott szaraz meres fogta meg.
TICK_STALE_FACTOR = 1.5      # egy periodus kimaradt + fel periodus tures
REARM_COOLDOWN_FACTOR = 1.35  # az uj /loop-nak legyen ideje egy tickel bizonyitani

#: Visszafele kompatibilis alapertekek (30 perces periodus).
TICK_STALE_S = int(DEFAULT_TICK_PERIOD_S * TICK_STALE_FACTOR)
REARM_COOLDOWN_S = int(DEFAULT_TICK_PERIOD_S * REARM_COOLDOWN_FACTOR)

#: A transcript vegebol ennyit nezunk vissza a tick-nyom kereseskor. A tick
#: 30 percenkent ir, tehat a nyom a fajl vegen van; a plafon miatt egy tobb
#: megabajtos naplo sem lesz 3 percenkenti teljes beolvasas.
TICK_SCAN_BYTES = 4 * 1024 * 1024


# ── Pure decisions ────────────────────────────────────────────────────────

def needs_oom_protect(current_adj: int | None,
                      target: int = AGENT_OOM_ADJ) -> bool:
    """Whether this PID still needs its OOM adjustment written.

    Unreadable (`None`) → False: the process is gone or not ours, and writing
    to a recycled PID would protect something arbitrary.
    """
    if current_adj is None:
        return False
    return current_adj != target


def should_rearm(*, transcript_age_s: float | None,
                 tick_age_s: float | None,
                 rearm_age_s: float | None,
                 proactive: bool,
                 has_loop_cmd: bool,
                 fresh_s: int = TRANSCRIPT_FRESH_S,
                 stale_s: float = TICK_STALE_S,
                 cooldown_s: float = REARM_COOLDOWN_S) -> bool:
    """Alive but not ticking → re-send the loop command?

    A `/loop` timer is a `CronCreate` job, and the tool says so itself:
    "Session-only … **Auto-expires after 7 days**." In one observed case
    the job fired its last tick exactly on the seventh day, and the agent then
    sat silent for 38 hours until a human wrote to it.

    The heartbeat above could not catch that, and it is important to see WHY:
    it answers "is this process alive", and the process WAS alive — it simply
    had no timer wound up. One signal cannot answer two questions. So this asks
    the second question, from a separate source (`tick_age_s`).

    The four conditions, each load-bearing:

    * `proactive` + `has_loop_cmd` — only agents that are supposed to tick, and
      only when the registry says what to re-send.
    * transcript **idle** — a busy agent writes continuously, so past the
      freshness window we know we are not injecting into a running release.
    * tick **stale** — measured against the agent's OWN period (1.5×), never a
      fixed number of minutes: for an agent ticking hourly a flat 45 minutes would
      have re-armed a perfectly healthy agent every single hour. `None` (no
      observable tick trace) is deliberately NOT stale: if a marker were
      misconfigured we would re-arm forever and pile up duplicate crons, each
      one doubling the tick rate. Silence we can see beats a storm we cannot.
    * cooldown — a fresh re-arm needs up to a full period to prove itself.
    """
    if not (proactive and has_loop_cmd):
        return False
    if transcript_age_s is None or transcript_age_s < fresh_s:
        return False
    if tick_age_s is None or tick_age_s <= stale_s:
        return False
    return rearm_age_s is None or rearm_age_s > cooldown_s


def rearm_reason(entry: dict, m: dict) -> str | None:
    """Pure: a liveness tick-őre (korábban külön timeren futott). Él, de
    nem tickel, és tétlen → a loop-parancs újraküldése. A küszöbök az ágens
    saját periódusából (should_rearm)."""
    if entry.get("tick_gate"):
        return None   # tick-kapu: a tick-kapu ütemez; a loop-parancs újraküldése kettős ütemet adna
    period = float(entry.get("tick_period_s") or DEFAULT_TICK_PERIOD_S)
    tick_age = (m["signals"]["schedule"].get("data") or {}).get("tick_age_s")
    if not should_rearm(transcript_age_s=m.get("transcript_age_s"), tick_age_s=tick_age,
                        rearm_age_s=m.get("rearm_age_s"),
                        proactive=bool(entry.get("proactive")),
                        has_loop_cmd=bool(entry.get("loop_cmd")),
                        stale_s=period * TICK_STALE_FACTOR,
                        cooldown_s=period * REARM_COOLDOWN_FACTOR):
        return None
    return f"él, tétlen, és {int((tick_age or 0) // 60)} perce nem tickelt — loop-parancs újraküldése"


# ── I/O ───────────────────────────────────────────────────────────────────

def read_session_id(agent: str) -> str | None:
    p = Path.home() / ".config" / agent / "session.id"
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def transcript_age_s(session_id: str, now: float | None = None) -> float | None:
    """Seconds since the session's transcript was last written, or None."""
    matches = sorted(Path.home().glob(f".claude/projects/*/{session_id}.jsonl"))
    if not matches:
        return None
    try:
        return (now or time.time()) - matches[0].stat().st_mtime
    except OSError:
        return None


#: A `pgrep` mintája. Az ágens-processz mindig a claude bináris,
#: `--dangerously-skip-permissions`-szal — ez a jel közös MINDEN ágensben,
#: függetlenül attól, hogy resume-mal vagy frissen indult.
CLAUDE_PATTERN = "claude --dangerously-skip-permissions"


def is_agent_cmdline(argv: list[str]) -> bool:
    """Ez a processz egy ágens-session? Tiszta, tehát tesztelhető.

    ⚠️ EZ KORÁBBAN `--resume <session_id>`-re illesztett, és az SZERKEZETILEG
    hibás volt: a session-azonosító CSAK akkor szerepel a parancssorban, ha az
    ágens folytat. Egy `--channels plugin:telegram`-mal induló ágens nem ilyen, egy
    újraindulás után pedig mindenki resume nélkül jön fel — a boxon mérve hét
    ágens-processzből NÉGY így láthatatlan maradt, vagyis a védelem pont a
    frissen indult (és ezért legsérülékenyebb) ágenseket hagyta ki.

    A helyes jel maga a bináris. A wrappereket (`/bin/sh -c …`, `tmux …`)
    kizárjuk: azok parancssorában szerepel ugyan a minta, de nem ők az ágens,
    és a `pgrep -f` rájuk is illeszkedne — beleértve egy olyan shell-parancsot
    is, ami éppen erre a mintára keres.
    """
    if not argv:
        return False
    return argv[0].endswith("/claude") and "--dangerously-skip-permissions" in " ".join(argv)


def _cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [x for x in raw.decode("utf-8", "replace").split("\0") if x]


def claude_pids() -> list[int]:
    """Minden futó ágens-session PID-je.

    SZÁNDÉKOSAN nem a registryből dolgozik. Az OOM-védelemhez nem kell tudni,
    MELYIK ágensről van szó — minden ágenst védeni akarunk, és egy registryből
    kimaradt ágens így sem esik ki a védelemből. A registry az
    ÉLETJEL-félhez kell, ahol a heartbeat helyét kell tudni.
    """
    r = subprocess.run(["pgrep", "-f", "--", CLAUDE_PATTERN],
                       capture_output=True, text=True)
    pids = [int(x) for x in r.stdout.split() if x.isdigit()]
    return [p for p in pids if is_agent_cmdline(_cmdline(p))]


def read_oom_adj(pid: int) -> int | None:
    try:
        return int(Path(f"/proc/{pid}/oom_score_adj").read_text().strip())
    except (OSError, ValueError):
        return None


def write_oom_adj(pid: int, value: int = AGENT_OOM_ADJ) -> bool:
    """Write the adjustment. Needs privilege for a negative value, hence sudo -n.

    Failure is not fatal and not loud: on a box without the sudoers entry this
    would otherwise fail every three minutes forever. The caller reports the
    count instead.
    """
    # Csak a validáló segédprogram (csak /proc/<szám>/oom_score_adj, -1000..1000); a
    # sudoers-bejegyzés ŐT illeti. A régi `tee /proc/[0-9]*/oom_score_adj` tartalék-út
    # kikerült (FL-02): klasszikus sudo alatt a `*` bármely karakterre illeszkedik, így
    # rootként bármely fájl írható volt; sudo-rs alatt pedig érvénytelen szabály.
    if not Path(OOM_HELPER).exists():
        return False
    try:
        p = subprocess.run(["sudo", "-n", OOM_HELPER, str(pid), str(value)],
                           input=str(value), capture_output=True, text=True)
    except OSError:
        return False
    return p.returncode == 0


def state_path(workdir: str, name: str) -> Path:
    d = workdir.replace("%h", str(Path.home()))
    return Path(d) / "data" / "state" / name


def _age_of(p: Path, now: float | None = None) -> float | None:
    try:
        return (now or time.time()) - p.stat().st_mtime
    except OSError:
        return None


def marker_age_s(session_id: str, marker: str, now: float | None = None) -> float | None:
    """Seconds since the loop last fired, read from the session transcript.

    The loop enqueues its prompt as a user message, so the tick leaves the
    marker text in the transcript with its own timestamp. This is the fallback
    for agents whose tick has no state file of its own (e.g. a `/<agent>:tick`
    skill), and it
    needs no cooperation from the agent's own repo.

    Only the tail is scanned: with a 30-minute cadence the trace is at the end
    of the file, and this runs every three minutes for every agent. No match in
    the window → `None` = "not observable", which `should_rearm` treats as
    "do nothing" rather than "stale" — see the storm argument there.
    """
    matches = sorted(Path.home().glob(f".claude/projects/*/{session_id}.jsonl"))
    if not matches:
        return None
    try:
        with matches[0].open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TICK_SCAN_BYTES))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return None

    stamp = None
    for line in tail.splitlines():
        if marker in line:
            m = re.search(r'"timestamp":"([^"]+)"', line)
            if m:
                stamp = m.group(1)
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (now or time.time()) - when.timestamp()


def tick_age_s(agent: dict, session_id: str, now: float | None = None) -> float | None:
    """How long since this agent's loop last fired, or None if not observable.

    Two independent sources, and we take the FRESHEST of the two:

    * `data/state/last-tick.json` — explicit and unambiguous, written by the
      agent's own tick (the anytime engine's `entry.py` does this).
    * the transcript marker — needs no cooperation from the agent's repo, and
      is the only source for agents with a skill-based tick.

    Taking the minimum rather than a priority order is deliberate. A state file
    that exists but stops being updated (a tick running from a different
    checkout, a wiped state dir left behind) would otherwise look permanently
    stale and we would re-arm every cooldown forever. Any evidence that a tick
    happened is evidence that the timer is alive.
    """
    ages = []
    f = state_path(agent.get("workdir", ""), "last-tick.json")
    if f.exists():
        ages.append(_age_of(f, now))
    marker = agent.get("tick_marker")
    if marker:
        ages.append(marker_age_s(session_id, marker, now))
    real = [a for a in ages if a is not None]
    return min(real) if real else None


def send_loop_cmd(session: str, loop_cmd: str) -> bool:
    """Type the loop command into the agent's tmux session.

    Deliberately NOT a `systemctl restart`: a restart would drop the live
    session and cost a resume, and the agent may be one message away from work.
    Re-arming is the smallest repair that fixes the actual fault.
    """
    try:
        r = subprocess.run(["tmux", "send-keys", "-t", session, loop_cmd, "Enter"],
                           capture_output=True, text=True)
        return r.returncode == 0
    except OSError:
        return False


def oom_sweep() -> dict:
    """OOM-védelem minden ágens-processzre, a registrytől FÜGGETLENÜL: egy
    nyilvántartásból kimaradt ágens sem esik ki. A reconcile hívja minden
    körben (egy vezérlő).

    A sikertelen írást KÜLÖN számoljuk. Amíg egy `and` kötötte össze a két
    feltételt, a "nem is kellett védeni" és a "minden próbálkozás elbukott"
    ugyanazt a nullát adta — egy boxon napokig így futott: az ágensek
    `oom_score_adj` értéke 200 maradt (a cél -600), mert a `sudo -n` tiltva
    volt, miközben a napló nyugalmat jelentett."""
    report = {"protected": 0, "oom_failed": 0, "helper_missing": not Path(OOM_HELPER).exists()}
    for pid in claude_pids():
        if not needs_oom_protect(read_oom_adj(pid)):
            continue
        if write_oom_adj(pid):
            report["protected"] += 1
        else:
            report["oom_failed"] += 1
    return report


def format_oom(r: dict) -> str:
    if r.get("oom_failed") and r.get("helper_missing"):
        why = (f"nincs {OOM_HELPER} — telepítés: sudo install -o root -g root -m 0755 "
               "~/src/mentat/fleet/bin/oom-protect " + OOM_HELPER)
    else:
        why = "sudo -n tiltva?"
    return (f"OOM-védelem: {r['protected']} beírva"
            + (f", {r['oom_failed']} NEM SIKERÜLT ({why})" if r.get("oom_failed") else ""))


def main() -> int:
    """A régi `agent-liveness.timer` belépője. A liveness a reconcile-ba
    olvadt: két vezérlő két íróval („két író, egy olvasó") nem
    maradhat. Ha egy boxon még fut a régi timer, ez nem csinál semmit — a
    `fleet install` leveszi."""
    print("liveness: beolvadt a reconcile-ba — ez a belépő nem csinál semmit; "
          "a régi agent-liveness.timert a `fleet install` eltávolítja", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
