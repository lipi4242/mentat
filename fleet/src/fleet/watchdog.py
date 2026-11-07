"""Shared crash-restart watchdog. Pure decision + systemd runner."""
from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import os, subprocess, time
from pathlib import Path
from fleet import registry_dir
from fleet import registry as reg
from fleet import maintenance
from fleet.registry import is_dormant, load_json


#: Alsó korlát a halottnak nyilvánításhoz. A küszöb SZÁRMAZTATOTT (lásd
#: `staleness_min_for`), de sosem eshet a ma működő 90 perc alá: egy
#: watchdog-küszöb, ami bárhol szigorít, álcázott regresszió — pont azt a
#: restart-hurkot hozná vissza, amit meg akarunk szüntetni.
STALENESS_FLOOR_MIN = 90

#: Hány tick-periódusnyi némaság után tekintjük halottnak. A 3-as azért ez,
#: mert 1800 s-nál PONT a padlót adja (3 × 30 perc = 90), tehát a ma 1800-on
#: futó négy ágens küszöbe változatlan — nulla regresszió, nincs "köztes
#: ablak", amiben bárki szigorúbb küszöböt kapna.
STALENESS_PERIOD_FACTOR = 3


def staleness_min_for(tick_period_s=None) -> int:
    """Az ágens SAJÁT tick_period_s-éből származtatott halottnak-nyilvánítási
    küszöb, percben.

    Ezt az elvet a testvérmodul (`liveness.py`) már követi és ki is mondja
    magáról: "Every threshold here is derived from the agent's own
    `tick_period_s`, never a [konstans]". A watchdog eddig fix 90-et használt
    mindenkire — így egy 3600 s-os periódusnál EGYETLEN kihagyott kör (≈120
    perc) is restartot hozott, egy napi kétszer futó ágenst pedig óránként
    újraindított volna.

    Hiányzó mező esetén a liveness alapértelmezését vesszük át (import, nem
    másolat — ugyanaz az érték két helyen kimondva pont a mai hibaosztály).
    """
    from fleet.liveness import DEFAULT_TICK_PERIOD_S
    period_s = float(tick_period_s or DEFAULT_TICK_PERIOD_S)
    return int(max(STALENESS_FLOOR_MIN, STALENESS_PERIOD_FACTOR * period_s / 60))


def agent_is_dead(*, session_alive: bool, proactive: bool,
                  heartbeat_age_min, staleness_min: int = STALENESS_FLOOR_MIN,
                  session_age_min=None, startup_grace_min: int = 15) -> bool:
    if not session_alive:
        return True
    if proactive:
        if session_age_min is not None and session_age_min < startup_grace_min:
            return False
        if heartbeat_age_min is None:
            return True
        return heartbeat_age_min > staleness_min
    return False


# A dead agent session leaves its Telegram-plugin `bun server.ts` child orphaned
# (reparented to systemd/init, not killed — the units run KillMode=none because
# they share one tmux server). Left unchecked these pile up one-per-failed-restart
# and thrash the box (observed: a restart spiral on a production box). A legit bun server is a
# child of `bun run ...` (parent comm 'bun'); an orphan's parent is systemd/init.
_ORPHAN_PARENT_COMMS = {"", "systemd", "init"}


def orphan_bun_pids(procs) -> list[int]:
    """Pure: from process records {pid, cmd, parent_comm}, return the pids of
    orphaned telegram-plugin bun servers safe to reap. Only reaps a `bun server.ts`
    whose parent comm is systemd/init/none (positively reparented) — never one still
    parented by a live `bun` (a legit, running plugin)."""
    out = []
    for p in procs:
        cmd = p.get("cmd", "") or ""
        if "server.ts" not in cmd or "bun" not in cmd:
            continue
        if (p.get("parent_comm") or "").strip() in _ORPHAN_PARENT_COMMS:
            out.append(p["pid"])
    return out


def _bun_procs():
    r = subprocess.run(["pgrep", "-f", "server.ts"], capture_output=True, text=True)
    procs = []
    for pid in r.stdout.split():
        def _ps(fmt, target):
            return subprocess.run(["ps", "-o", fmt, "-p", target],
                                  capture_output=True, text=True).stdout.strip()
        cmd = _ps("cmd=", pid)
        ppid = _ps("ppid=", pid)
        pcomm = _ps("comm=", ppid) if ppid else ""
        procs.append({"pid": int(pid), "cmd": cmd, "parent_comm": pcomm})
    return procs


def reap_orphan_bun() -> None:
    """Reap orphaned telegram bun servers. Best-effort — never raises."""
    try:
        for pid in orphan_bun_pids(_bun_procs()):
            print(f"[watchdog] reaping orphaned bun server {pid}")
            subprocess.run(["kill", "-9", str(pid)])
    except Exception as e:  # noqa: BLE001
        print(f"[watchdog] orphan-reap skipped: {e}")


def _session_alive(session: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", session],
                          capture_output=True).returncode == 0


def _session_age_min(session: str):
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-p", "-t", session, "#{session_created}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return None
        created = float(r.stdout.strip())
        return (time.time() - created) / 60.0
    except Exception:
        return None


def _heartbeat_age_min(workdir: str):
    hb = Path(workdir.replace("%h", str(Path.home()))) / "data/state/orchestrator-heartbeat.json"
    if not hb.exists():
        return None
    return (time.time() - hb.stat().st_mtime) / 60.0


def _host_matches(entry, host):
    """Ez a gép őrzi-e ezt az ágenst.

    A gép kulcsát a `registry.local_host()` adja (FLEET_HOST env →
    ~/.config/fleet/host → boxes.json hostname). Nincs személyes vagy
    beégetett alapérték: ismeretlen gépen (None) csak a host nélküli
    bejegyzéseket őrizzük.
    """
    return reg.host_matches(entry, host)


def main() -> int:
    reap_orphan_bun()
    rdir = registry_dir()
    agents = load_json(rdir / "agents.json", [])
    host = reg.local_host(reg.load_boxes(rdir / "boxes.json"))
    for a in agents:
        try:
            # Dormant = desired-off. Restarting one would undo an operator
            # decision, so the skip comes before every liveness question.
            # Silent: this is steady state, not an event worth 288 log lines/day.
            if is_dormant(a):
                continue
            if maintenance.is_locked(a.get("agent", "")):
                print(f"[watchdog] {a.get('agent')}: maintenance lock active — skipping",
                      file=sys.stderr)
                continue
            if not _host_matches(a, host):
                continue
            session = a["session"]
            dead = agent_is_dead(
                session_alive=_session_alive(session),
                proactive=a.get("proactive", False),
                heartbeat_age_min=_heartbeat_age_min(a["workdir"]),
                staleness_min=staleness_min_for(a.get("tick_period_s")),
                session_age_min=_session_age_min(session),
            )
            if dead:
                unit = a.get("unit", f"{a.get('agent', 'unknown')}.service")
                print(f"[watchdog] restarting {a.get('agent')} ({unit})")
                r = subprocess.run(["systemctl", "--user", "restart", unit])
                if r.returncode != 0:
                    print(f"[watchdog] warning: restart of {unit} exited {r.returncode}")
        except Exception as e:
            print(f"[watchdog] skipping malformed entry: {e}")
            continue
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
