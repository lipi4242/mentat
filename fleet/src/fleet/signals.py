"""A négy jel. Négy külön kérdés, négy külön forrás, és mindegyiknél a
"nem mérhető" külön érték — sosem néz ki úgy, mint az "egészséges" vagy a
"rossz" (README 1. szabály; Codex F0-review).

  processz  — fut-e a claude bináris a várt `--remote-control <rc_name>`-mel
  ütemezés  — landolt-e tick a saját periódusán belül
  csatorna  — a híd health-fájlja friss-e, van-e 409 a journalban
  RC        — a FUTÓ processz indulása óta mi az utolsó RC-esemény
  auth      — él-e a Claude-login (authsig.py): a lejárt login mellett a
              másik négy jel zöld marad, ezért külön jel (2026-10-01)

Minden mérő tiszta függvényre és egy vékony I/O-ra van bontva, hogy a döntés
tesztelhető legyen systemd, tmux és /proc nélkül.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from fleet.liveness import (read_session_id, transcript_age_s, tick_age_s,
                            DEFAULT_TICK_PERIOD_S, TICK_STALE_FACTOR, is_agent_cmdline)

UNKNOWN = "unknown"


def claude_home(entry: dict) -> Path:
    """A Claude-könyvtár, amiben az ágens transzkriptje él: a közös ~/.claude,
    vagy a nevesített fiók ~/.claude-<fiók> könyvtára."""
    acc = entry.get("claude_account") or "shared"
    return Path.home() / (".claude" if acc == "shared" else f".claude-{acc}")


def transcript_path(entry: dict, sid: str | None) -> Path | None:
    if not sid:
        return None
    m = sorted(claude_home(entry).glob(f"projects/*/{sid}.jsonl"))
    return m[0] if m else None


@dataclass
class Signal:
    name: str
    state: str          # per-signal vocabulary; UNKNOWN közös
    detail: str = ""
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


# ── processz ──────────────────────────────────────────────────────────────

def _proc_records() -> list[dict]:
    """{pid, ppid, rss_mb, started_s, argv} minden processzre. Linux (/proc);
    máshol üres lista → UNKNOWN, nem 'down'."""
    out = []
    proc = Path("/proc")
    if not proc.is_dir():
        return out
    try:
        boot = None
        for line in (proc / "stat").read_text().splitlines():
            if line.startswith("btime "):
                boot = int(line.split()[1])
        hz = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError):
        return out
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            argv = [x for x in (p / "cmdline").read_bytes().decode("utf-8", "replace").split("\0") if x]
            stat = (p / "stat").read_text().rsplit(")", 1)[1].split()
            ppid = int(stat[1])
            start_ticks = int(stat[19])
            rss_pages = int(stat[21])
        except (OSError, ValueError, IndexError):
            continue
        out.append({"pid": int(p.name), "ppid": ppid, "argv": argv,
                    "rss_mb": rss_pages * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024),
                    "started_s": (boot + start_ticks // hz) if boot is not None else None})
    return out


def find_agent_process(entry: dict, procs: list[dict]) -> dict | None:
    """Pure: az ágens claude-processze a processz-listából, vagy None.
    A jel: a bináris + `--remote-control <rc_name>`. A wrapper (sh, tmux)
    argv-je is tartalmazza a mintát, ezért a binárisra is szűrünk."""
    want = ["--remote-control", entry["rc_name"]]
    hits = []
    for p in procs:
        argv = p["argv"]
        if not is_agent_cmdline(argv):
            continue
        if any(argv[i] == want[0] and argv[i + 1] == want[1] for i in range(len(argv) - 1)):
            hits.append(p)
    # Újraindításkor egy pillanatig a régi és az új claude is él: a legfrissebb az ágens.
    return max(hits, key=lambda p: (p.get("started_s") or 0, p["pid"])) if hits else None


def process_signal(entry: dict, procs: list[dict] | None = None) -> Signal:
    procs = _proc_records() if procs is None else procs
    if not procs:
        return Signal("process", UNKNOWN, "nincs /proc — nem mérhető")
    p = find_agent_process(entry, procs)
    if p is None:
        return Signal("process", "down", f"nincs claude-processz --remote-control {entry['rc_name']}")
    return Signal("process", "up", f"pid {p['pid']}, {p['rss_mb']} MB",
                  {"pid": p["pid"], "rss_mb": p["rss_mb"], "started_s": p["started_s"]})


def descendants(pid: int, procs: list[dict]) -> list[dict]:
    """Pure: egy processz minden leszármazottja."""
    by_parent: dict[int, list[dict]] = {}
    for p in procs:
        by_parent.setdefault(p["ppid"], []).append(p)
    out, stack = [], [pid]
    while stack:
        cur = stack.pop()
        for c in by_parent.get(cur, []):
            out.append(c)
            stack.append(c["pid"])
    return out


def plugin_pollers(agent_pid: int | None, procs: list[dict]) -> list[dict]:
    """Pure: a telegram-plugin pollerei (bun server.ts) az ágens processze
    ALATT. Csak a leszármazottakat: egy másik ágens pollerét nem a mi dolgunk
    leölni, és egy árva (init alatti) poller a `watchdog.reap_orphan_bun` dolga."""
    if agent_pid is None:
        return []
    return [p for p in descendants(agent_pid, procs)
            if "server.ts" in " ".join(p["argv"]) and "bun" in " ".join(p["argv"])]


# ── ütemezés ──────────────────────────────────────────────────────────────

def schedule_verdict(*, proactive: bool, tick_age: float | None, period_s: float,
                     process_started_s: int | None, now: float) -> tuple[str, str]:
    """Pure. 'n/a' nem proaktív ágensre; 'armed' ha a tick a periódus
    1,5-szeresén belül van; 'pending' ha a processz fiatalabb, mint egy
    periódus + indulási fej (még nem várható tick); 'stale' ha ennél tovább
    nincs friss tick — AKKOR IS, ha egyáltalán nincs tick-nyom: a türelmi idő
    után a 'pending' nem válhat 'unknown'-ná (egy startup-parancs 30
    napig nem ment be, és ez sehol nem látszott rossznak). 'unknown' csak ha
    a processz indulása sem ismert, tehát a türelmi idő sem dönthető el."""
    if not proactive:
        return "n/a", "nem proaktív"
    if tick_age is None:
        if process_started_s is None:
            return UNKNOWN, "nincs tick-nyom (last-tick.json / marker), és a processz indulása sem ismert"
        up = now - process_started_s
        if up < period_s + 180:
            return "pending", "friss indulás, még nem várható tick"
        return "stale", (f"a processz {int(up // 3600)} órája fut, és nincs egyetlen tick-nyom sem "
                         "(last-tick.json / marker) — a loop nem húzódott fel, vagy a tick-nyom nincs beállítva")
    if tick_age <= period_s * TICK_STALE_FACTOR:
        return "armed", f"utolsó tick {int(tick_age // 60)} perce"
    if process_started_s is not None and now - process_started_s < period_s + 180:
        return "pending", f"restart után {int((now - process_started_s) // 60)} perce, tick még nem várható"
    return "stale", f"utolsó tick {int(tick_age // 3600)} órája (periódus {int(period_s // 60)} perc)"


def schedule_signal(entry: dict, sid: str | None, process_started_s: int | None,
                    now: float | None = None) -> Signal:
    now = now or time.time()
    from fleet.tick_watch import fleet_tick
    ft = fleet_tick(entry, Path.home(), now)
    if ft is not None:
        # a flotta timere tickel (schedule_owner: fleet) — a proactive-tól függetlenül figyelt
        state, detail = schedule_verdict(proactive=True, tick_age=ft["tick_age"], period_s=ft["period_s"],
                                         process_started_s=ft["armed_since"], now=now)
        return Signal("schedule", state, f"flotta-timer: {detail}",
                      {"tick_age_s": ft["tick_age"], "period_s": ft["period_s"], "owner": "fleet",
                       # egyetlen tick sem landolt: a csend az élesítés óta tart
                       "silent_s": ft["tick_age"] if ft["tick_age"] is not None else
                       (now - ft["armed_since"] if ft["armed_since"] else None)})
    period = float(entry.get("tick_period_s") or DEFAULT_TICK_PERIOD_S)
    age = tick_age_s(entry, sid, now) if sid else None
    state, detail = schedule_verdict(proactive=bool(entry.get("proactive")), tick_age=age,
                                     period_s=period, process_started_s=process_started_s, now=now)
    return Signal("schedule", state, detail, {"tick_age_s": age, "period_s": period})


# ── csatorna ──────────────────────────────────────────────────────────────

def health_path(agent: str) -> Path:
    return Path.home() / ".config" / agent / "telegram-state" / "health.json"


def journal_409_count(unit: str, since: str = "-10min") -> int | None:
    try:
        r = subprocess.run(["journalctl", "--user", "-u", unit, "--since", since, "--no-pager", "-q"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return sum(1 for line in r.stdout.splitlines() if "409" in line and "Conflict" in line)


def channel_verdict(*, has_bridge: bool, health_age_s: float | None,
                    conflicts_10min: int | None, stale_s: float = 300.0) -> tuple[str, str]:
    """Pure. 'n/a' híd nélkül; 'conflict' ha 409 van; 'stale' ha a health
    öreg; 'unknown' ha egyik sem mérhető; különben 'ok'."""
    if not has_bridge:
        return "n/a", "nincs híd"
    if conflicts_10min:
        return "conflict", f"{conflicts_10min} db 409 az elmúlt 10 percben — másik poller fogja a tokent"
    if health_age_s is None:
        return (UNKNOWN, "nincs health.json és a journal sem mérhető") if conflicts_10min is None \
            else (UNKNOWN, "nincs health.json (409: 0)")
    if health_age_s > stale_s:
        return "stale", f"health.json {int(health_age_s // 60)} perce nem frissült"
    return "ok", f"health {int(health_age_s)} s, 409: {conflicts_10min if conflicts_10min is not None else '?'}"


def channel_signal(entry: dict, now: float | None = None) -> Signal:
    now = now or time.time()
    bridge = entry.get("bridge") or {}
    has = bool(bridge.get("unit"))
    age = None
    p = health_path(entry["agent"])
    try:
        d = json.loads(p.read_text())
        wa = d.get("written_at")
        if wa:
            age = now - float(wa) / 1000.0
    except (OSError, ValueError, json.JSONDecodeError):
        age = None
    conf = journal_409_count(bridge["unit"]) if has else None
    state, detail = channel_verdict(has_bridge=has, health_age_s=age, conflicts_10min=conf)
    return Signal("channel", state, detail, {"health_age_s": age, "conflicts_10min": conf})


# ── RC ────────────────────────────────────────────────────────────────────

_RC_RE = re.compile(r"Remote Control (disconnected|connected)")
_TS_RE = re.compile(r'"timestamp":"([^"]+)"')


def rc_events(lines: list[str]) -> list[tuple[float, str]]:
    """Pure: (epoch, 'connected'|'disconnected') a transzkript soraiból."""
    from datetime import datetime
    out = []
    for line in lines:
        m = _RC_RE.search(line)
        if not m:
            continue
        t = _TS_RE.search(line)
        if not t:
            continue
        try:
            when = datetime.fromisoformat(t.group(1).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        out.append((when, m.group(1)))
    return out


def rc_verdict(events: list[tuple[float, str]], process_started_s: int | None) -> tuple[str, str]:
    """Pure. Csak a futó processz indulása UTÁNI események számítanak — egy
    régi 'disconnected' nem hozhat restartot (Codex F0-review 3. pont).

    MÉRT KORLÁT (2026-09-17, éles box): a transzkript a leszakadást
    naplózza, a visszakapcsolódást NEM. Egy ágensnél a "disconnected" sor után
    az RC bizonyítottan újra működött. Ezért a transzkriptből az RC jelenlegi
    állapota nem dönthető el — a jel itt legfeljebb "unknown, utolsó ismert
    esemény: …". Az állapotot a plugin-oldali roster (ListAgents) méri.
    Restartot vagy riasztást erre a jelre alapozni tilos."""
    if process_started_s is None:
        return UNKNOWN, "nincs processz-indulási idő"
    recent = [e for e in events if e[0] >= process_started_s - 5]
    if not recent:
        return UNKNOWN, "nincs RC-esemény a processz indulása óta"
    when, last = recent[-1]
    from datetime import datetime
    stamp = datetime.fromtimestamp(when).strftime("%m-%d %H:%M")
    if last == "connected":
        return "connected", f"utolsó esemény: connected ({stamp})"
    return UNKNOWN, f"utolsó ismert esemény: disconnected ({stamp}) — a visszakapcsolódás nem naplózódik, az állapotot a ListAgents méri"


def rc_signal(entry: dict, sid: str | None, process_started_s: int | None,
              scan_bytes: int = 8 * 1024 * 1024) -> Signal:
    if not sid:
        return Signal("rc", UNKNOWN, "nincs session.id")
    tp = transcript_path(entry, sid)
    if tp is None:
        return Signal("rc", UNKNOWN, "nincs transzkript")
    try:
        with tp.open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - scan_bytes))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return Signal("rc", UNKNOWN, "transzkript nem olvasható")
    state, detail = rc_verdict(rc_events(tail), process_started_s)
    return Signal("rc", state, detail)


# ── összegzés ─────────────────────────────────────────────────────────────

def _auth(entry: dict, sid: str | None) -> dict:
    from fleet.authsig import auth_signal   # külön modul, körkörös import nélkül
    return auth_signal(entry, sid).as_dict()


def measure(entry: dict, procs: list[dict] | None = None) -> dict:
    """Mind a négy jel egy ágensre, plusz a nyers adatok, amikre a reconcile
    épít (pid, pollerek, transzkript kora)."""
    procs = _proc_records() if procs is None else procs
    sid = read_session_id(entry["agent"])
    proc = process_signal(entry, procs)
    pid = proc.data.get("pid")
    started = proc.data.get("started_s")
    tp = transcript_path(entry, sid)
    try:
        t_age = (time.time() - tp.stat().st_mtime) if tp else None
    except OSError:
        t_age = None
    return {
        "agent": entry["agent"],
        "session_id": sid,
        "transcript_age_s": t_age,
        "pollers": [p["pid"] for p in plugin_pollers(pid, procs)],
        "signals": {
            "process": proc.as_dict(),
            "schedule": schedule_signal(entry, sid, started).as_dict(),
            "channel": channel_signal(entry).as_dict(),
            "rc": rc_signal(entry, sid, started).as_dict(),
            "auth": _auth(entry, sid),
        },
    }
