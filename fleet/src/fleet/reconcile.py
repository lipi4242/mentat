"""Kívánt állapot érvényesítése — az 5 perces timer. A watchdog utódja.

A watchdog egy dolgot tudott: újraindítani. Ez a modul a registry KÍVÁNT
állapotát érvényesíti (dormant → áll, active → fut és egészséges), és minden
beavatkozás után megnézi a mellékhatásokat (postcheck). A döntések tiszták
(`decide`), a végrehajtás injektálható.

Tulajdonjog (Codex F0-review 1. pont): két vezérlő nem futhat egyszerre.
Beavatkozni csak akkor szabad, ha `~/.config/fleet/controller` tartalma
`reconcile`. Amíg nem az, a modul MEGFIGYEL: ugyanazt a döntést kiírja, de
nem hajtja végre, és nem is ír állapotot. A cutover ezt a fájlt írja —
miután a régi watchdog-timer leállt.

Zárak és sorrend (Codex F1-review):
  * egy futás egyszerre: `state/reconcile.lock` (flock); ha foglalt, kilép
  * a restart-kísérlet ELŐBB kerül lemezre, mint a systemctl hívás
  * a tulajdonjog, a karbantartási zár és a karantén KÖZVETLENÜL a beavatkozás
    előtt újra ellenőrződik, nem a kör elején
  * sérült állapotfájl → nem nyúlunk az ágenshez (nem "üres költségvetés")
  * ismeretlen host → csak megfigyelés

Költségvetés: ágensenként legfeljebb RESTART_BUDGET restart (és ugyanennyi
híd-restart) egy órán belül; QUARANTINE_AFTER egymást követő `failed`
postcheck → `quarantined`: a reconcile nem nyúl hozzá, riaszt, és ember
oldja fel (`fleet unquarantine`). A kért leállás (`fleet stop`) utáni EGY
visszaindítás nem fogy a költségvetésből (`requested_stop`), hanem a
`requested_restarts` listába kerül; a postcheck és a karantén ugyanúgy él.
"""
from __future__ import annotations
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fleet import CONFIG_DIR, alerts, dup, maintenance, requested_stop, signals
from fleet.registry import is_dormant, load_agents, agents_for_host, local_host
from fleet import liveness
from fleet.liveness import TRANSCRIPT_FRESH_S
from fleet.postcheck import postcheck, OK, PENDING, FAILED, window_s

CONTROLLER_PATH = CONFIG_DIR / "controller"
STATE_DIR = CONFIG_DIR / "state"
LOCK_PATH = STATE_DIR / "reconcile.lock"

RESTART_BUDGET = 3          # restart / óra / ágens
BUDGET_WINDOW_S = 3600
QUARANTINE_AFTER = 2        # egymást követő bukott postcheck
MEMORY_MAX_MB = int(os.environ.get("FLEET_MEMORY_MAX_MB", "1100"))
MEMORY_ACT = os.environ.get("FLEET_MEMORY_GUARD", "report") == "act"
SILENCE_PERIODS = 12        # ennyi kihagyott periódus után riasztás

CORRUPT = object()


# ── állapot ───────────────────────────────────────────────────────────────

def state_path(agent: str) -> Path:
    return STATE_DIR / f"{agent}.json"


def empty_state() -> dict:
    return {"restarts": [], "bridge_restarts": [], "failed_postchecks": 0,
            "quarantined": False, "pending_postcheck": None}


def load_state(agent: str):
    """dict, vagy CORRUPT, ha van fájl, de nem olvasható — az NEM üres
    költségvetés, hanem "ne nyúlj hozzá"."""
    p = state_path(agent)
    if not p.exists():
        return empty_state()
    try:
        st = json.loads(p.read_text())
        if not isinstance(st, dict):
            return CORRUPT
        base = empty_state(); base.update(st)
        return base
    except (OSError, json.JSONDecodeError):
        return CORRUPT


def save_state(agent: str, st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = state_path(agent)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2))
    os.replace(tmp, p)


def controller_is_us() -> bool:
    try:
        return CONTROLLER_PATH.read_text().strip() == "reconcile"
    except OSError:
        return False


# ── tiszta döntés ─────────────────────────────────────────────────────────

def _left(stamps: list, now: float) -> int:
    recent = [t for t in stamps if now - t < BUDGET_WINDOW_S]
    return max(0, RESTART_BUDGET - len(recent))


def budget_left(st: dict, now: float) -> int:
    return _left(st.get("restarts", []), now)


def decide(entry: dict, m: dict, st, *, unit_active: bool | None,
           locked: bool, now: float, requested: bool = False) -> list[tuple[str, str]]:
    """Pure: [(művelet, indok)]. Műveletek:
    stop · start · restart · kill_pollers · restart_bridge · planned_restart ·
    recheck · alert:<kulcs> · noop · skip:<ok>"""
    a = entry["agent"]
    if st is CORRUPT:
        return [("skip:state-corrupt", "az állapotfájl sérült — ember nézze meg")]
    if locked:
        return [("skip:lock", "karbantartási zár")]
    if is_dormant(entry):
        if unit_active or m["signals"]["process"]["state"] == "up":
            return [("stop", "dormant, de fut")]
        return [("noop", "dormant, áll")]
    if st.get("quarantined"):
        return [("skip:quarantine", "karantén — ember oldja fel")]
    if unit_active is None:
        return [("skip:unmeasurable", "a systemd nem válaszol")]
    s = m["signals"]
    proc = s["process"]["state"]
    acts: list[tuple[str, str]] = []
    if proc == signals.UNKNOWN:
        return [("skip:unmeasurable", "a processz nem mérhető ezen a gépen")]
    if proc == "down":
        if requested:
            return [("start" if not unit_active else "restart", "kért leállás (fleet stop) után — nem fogy a költségvetésből")]
        if budget_left(st, now) == 0:
            return [(f"alert:budget:{a}", f"{a}: {RESTART_BUDGET} restart/óra elfogyott, nem indítom újra")]
        return [("start" if not unit_active else "restart", "nincs claude-processz")]
    # fut — függő postcheck?
    pp = st.get("pending_postcheck")
    if pp:
        acts.append(("recheck", f"függő postcheck a {int((now - pp['restart_at']) // 60)} perce indított restart után"))
    # mellékhatások
    if m["pollers"]:
        acts.append(("kill_pollers", f"telegram-plugin poller az ágens alatt: {m['pollers']}"))
    elif s["channel"]["state"] == "conflict":
        if _left(st.get("bridge_restarts", []), now) > 0:
            acts.append(("restart_bridge", s["channel"]["detail"]))
        else:
            acts.append((f"alert:bridge-budget:{a}", f"{a}: a híd {RESTART_BUDGET}× újraindítva egy órán belül, "
                         f"még mindig 409 — {dup.HINT_409}"))
    if s["rc"]["state"] == "disconnected":
        acts.append((f"alert:rc:{a}:{s['process']['data'].get('started_s')}",
                     f"{a}: RC leszakadt a futó processz alatt — restart javítja, kézzel"))
    auth = s.get("auth") or {}
    if auth.get("state") == "expired":
        # restart nem gyógyítja; a kulcs a lejárat ideje, hogy egy új lejárat új riasztás legyen
        acts.append((f"alert:auth:{a}:{int(auth.get('data', {}).get('since_s') or 0)}",
                     f"{a}: lejárt a Claude-login — {auth.get('detail', '')}"))
    rss = s["process"]["data"].get("rss_mb") or 0
    idle = (m.get("transcript_age_s") or 0) > TRANSCRIPT_FRESH_S
    if rss > MEMORY_MAX_MB:
        if MEMORY_ACT and idle and budget_left(st, now) > 0:
            acts.append(("planned_restart", f"{rss} MB > {MEMORY_MAX_MB} MB, idle"))
        else:
            acts.append((f"alert:memory:{a}:{rss // 200}", f"{a}: {rss} MB memória (küszöb {MEMORY_MAX_MB})"))
    sch = s["schedule"]
    if sch["state"] == "stale":
        period = sch["data"].get("period_s") or 1800
        age = sch["data"].get("tick_age_s") or sch["data"].get("silent_s") or 0
        # a csend-küszöb ágensenként a registryből (silence_after_s), különben
        # SILENCE_PERIODS × periódus — egy félórás ágensnél 6 óra a helyes, nem 72
        limit = float(entry.get("silence_after_s") or period * SILENCE_PERIODS)
        if age > limit:
            acts.append((f"alert:silence:{a}:{int(age // limit)}",
                         f"{a}: {int(age // 3600)} órája nem tickelt (periódus {int(period // 60)} perc)"))
    rearm = liveness.rearm_reason(entry, m)
    if rearm:
        acts.append(("rearm", rearm))
    if not acts:
        return [("noop", "egészséges")]
    # az ismeretlen mellékjelek nem "egészséges": ki is mondjuk
    unknown = [k for k in ("schedule", "channel", "rc", "auth") if k in s and s[k]["state"] == signals.UNKNOWN]
    if unknown and all(x[0].startswith("alert:") or x[0] == "recheck" for x in acts):
        acts.append(("noop", f"nem mérhető: {', '.join(unknown)}"))
    return acts


# ── végrehajtás ───────────────────────────────────────────────────────────

def _sysctl(*args: str) -> int:
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True).returncode
    except OSError:
        return 1


def _unit_active(unit: str) -> bool | None:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True)
    except OSError:
        return None
    out = r.stdout.strip()
    if out in ("active", "activating", "reloading"):
        return True
    if out in ("inactive", "failed", "deactivating"):
        return False
    return None


def _env_paths(entry: dict) -> list[Path]:
    """A riasztás a unit összes env-fájlját látja (11-07: az agent.env-es ágens tokenje a telegram.env-ben)."""
    from fleet.registry import env_files
    return [Path.home() / ".config" / entry["agent"] / f for f in env_files(entry)]


def _may_act(entry: dict, log) -> bool:
    """Közvetlenül a beavatkozás előtt: tulajdonjog, zár, karantén újra."""
    a = entry["agent"]
    if not controller_is_us():
        log(f"{a}: a tulajdonjog időközben elveszett — nem hajtom végre")
        return False
    if maintenance.is_locked(a):
        log(f"{a}: időközben karbantartási zár került rá — nem hajtom végre")
        return False
    st = load_state(a)
    if st is CORRUPT or st.get("quarantined"):
        log(f"{a}: állapot sérült vagy karantén — nem hajtom végre")
        return False
    return True


def _record_postcheck(entry: dict, st: dict, r: dict, *, log) -> None:
    a = entry["agent"]
    env_file = _env_paths(entry)
    if r["status"] == OK:
        st["failed_postchecks"] = 0
        st["pending_postcheck"] = None
        alerts.clear(f"rc:{a}")
        alerts.clear(f"kepesseg:{a}:")
        log(f"{a}: postcheck OK")
        try:  # 11-07: a postcheck a képességet is mérte — a központ a következő körben zöldet lát
            from fleet import flotta_report, kepesseg_riaszt
            kepesseg_riaszt.record(a, [])
            if flotta_report.config() is not None:
                flotta_report.force()
        except OSError as e:
            log(f"{a}: képesség-állapot nem írható ({type(e).__name__})")
    elif r["status"] == PENDING:
        log(f"{a}: postcheck PENDING — {'; '.join(r['pending'])}")
    elif r.get("capability_only"):
        # 11-07: él, de nem tud küldeni/todózni/gitezni — restart ezen nem segít, karantén sem;
        # a riasztás a beteg csatornától független úton megy: a központi flotta-ellenőrzésbe
        # (11-07), annak hiányában a fájl-tartalékba — a saját hídján soha
        st["pending_postcheck"] = None
        log(f"{a}: postcheck KÉPESSÉG-HIBA: {'; '.join(r['problems'])}")
        from fleet import kepesseg_riaszt
        log(f"{a}: riasztás [{kepesseg_riaszt.alert_red(a, r['problems'])}] képesség")
    else:
        st["failed_postchecks"] = st.get("failed_postchecks", 0) + 1
        st["pending_postcheck"] = None
        log(f"{a}: postcheck HIBA: {'; '.join(r['problems'])}")
        if st["failed_postchecks"] >= QUARANTINE_AFTER:
            st["quarantined"] = True
            alerts.alert(f"quarantine:{a}", f"⛔ {a}: {QUARANTINE_AFTER} bukott postcheck, karanténban. "
                         f"Utolsó: {'; '.join(r['problems'])}", agent_env_file=env_file)
    save_state(a, st)


def execute(entry: dict, action: str, m: dict, st: dict, *, now: float, log,
            sysctl=_sysctl, run=subprocess.run, do_postcheck=postcheck) -> None:
    a = entry["agent"]; unit = entry["unit"]
    bridge_unit = (entry.get("bridge") or {}).get("unit")
    env_file = _env_paths(entry)
    if action.startswith("alert:"):
        key = action[len("alert:"):]
        res = alerts.alert(key, m.get("_reason", key), agent_env_file=env_file)
        log(f"{a}: riasztás [{res}] {key}")
        return
    if not _may_act(entry, log):
        return
    if action == "stop":
        sysctl("stop", unit); sysctl("disable", unit)
        if bridge_unit:
            sysctl("stop", bridge_unit); sysctl("disable", bridge_unit)
        run(["tmux", "kill-session", "-t", f"={entry['session']}"], capture_output=True)
        for pid in m["pollers"]:
            run(["kill", str(pid)], capture_output=True)
        log(f"{a}: leállítva (dormant)")
    elif action in ("start", "restart", "planned_restart"):
        # a kísérlet ELŐBB kerül lemezre, mint a hívás; a kért leállás utáni
        # (egyszer felhasznált jelölő) nem fogy a crash-loop költségvetésből
        free = action != "planned_restart" and requested_stop.take(a, now)
        st.setdefault("requested_restarts" if free else "restarts", []).append(now)
        st["pending_postcheck"] = {"restart_at": now}
        save_state(a, st)
        sysctl("enable", unit)
        rc = sysctl("restart" if action != "start" else "start", unit)
        if rc != 0:
            st["failed_postchecks"] = st.get("failed_postchecks", 0) + 1
            st["pending_postcheck"] = None
            save_state(a, st)
            log(f"{a}: systemctl {action} hibával tért vissza ({rc})")
            return
        r = do_postcheck(entry, restart_at=now)
        _record_postcheck(entry, st, r, log=log)
        log(f"{a}: {action} végrehajtva")
    elif action == "recheck":
        pp = st.get("pending_postcheck") or {}
        r = do_postcheck(entry, restart_at=pp.get("restart_at"), wait_s=0)
        _record_postcheck(entry, st, r, log=log)
    elif action == "kill_pollers":
        for pid in m["pollers"]:
            run(["kill", str(pid)], capture_output=True)
        log(f"{a}: poller leölve: {m['pollers']}")
    elif action == "rearm":
        # a jelölő ELŐBB készül el, mint a küldés: egy bukott send-keys se
        # próbálkozzon 5 percenként (cooldown)
        mark = liveness.state_path(entry.get("workdir", ""), "last-rearm")
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.touch()
        ok = liveness.send_loop_cmd(entry["session"], entry.get("loop_cmd") or "")
        log(f"{a}: loop-parancs újraküldve" + ("" if ok else " — send-keys HIBA"))
    elif action == "restart_bridge" and bridge_unit:
        st.setdefault("bridge_restarts", []).append(now)
        save_state(a, st)
        sysctl("restart", bridge_unit)
        log(f"{a}: híd újraindítva (409)")


def reconcile(*, observe: bool = False, only: str | None = None, now: float | None = None,
              agents: list[dict] | None = None, measure=signals.measure,
              unit_active=_unit_active, execute_fn=execute, oom_sweep=liveness.oom_sweep,
              procs=signals._proc_records, fast: bool = False) -> dict:
    now = now or time.time()
    lines: list[str] = []
    log = lines.append
    acted = False
    host = local_host()
    acting = (not observe) and controller_is_us() and host is not None
    if host is None:
        log("reconcile: ez a gép nincs a boxes.json-ban és nincs FLEET_HOST — csak megfigyelés")
    mode = "ACT" if acting else "OBSERVE"
    if fast and not acting:
        return {"mode": mode, "host": host, "lines": []}   # a gyors út csak cselekvésre való
    log(f"reconcile [{mode}] host={host}")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w") as lockf:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log("reconcile: már fut egy példány — kilépek")
            return {"mode": mode, "host": host, "lines": [] if fast else lines}
        if acting and not fast:
            # a liveness OOM-söprése: minden ágens-processzre, a registrytől függetlenül
            log(liveness.format_oom(oom_sweep()))
        all_agents = agents if agents is not None else load_agents()
        for fe, pid in ([] if fast else dup.foreign_here(all_agents, host, procs() if procs else [])):
            msg = dup.dup_message(fe, pid, host)
            log(msg + ("" if acting else " (nem riasztok: megfigyelés)"))
            if acting:
                alerts.alert(f"dup:{fe['agent']}:{host}", msg,
                             agent_env_file=_env_paths(fe))
        for e in agents_for_host(host or "", all_agents):
            if only and e["agent"] != only:
                continue
            if e.get("supervision") == "none":
                log(f"{e['agent']}: supervision=none — kihagyva")
                continue
            if acting and not e.get("host"):
                log(f"{e['agent']}: nincs explicit host — nem nyúlok hozzá")
                continue
            st = load_state(e["agent"])
            m = measure(e)
            m.setdefault("rearm_age_s", liveness._age_of(liveness.state_path(e.get("workdir", ""), "last-rearm")))
            acts = decide(e, m, st, unit_active=unit_active(e["unit"]),
                          locked=maintenance.is_locked(e["agent"]), now=now,
                          requested=requested_stop.pending(e["agent"], now))
            if fast:
                from fleet import reconcile_fast
                acts = reconcile_fast.filter_acts(e["agent"], acts, now)
                acted = acted or bool(acts)
            for action, reason in acts:
                if action == "noop" or action.startswith("skip:"):
                    log(f"{e['agent']}: {action} — {reason}")
                    continue
                log(f"{e['agent']}: {action} — {reason}" + ("" if acting else " (nem hajtom végre)"))
                if acting:
                    m["_reason"] = reason
                    execute_fn(e, action, m, st, now=now, log=log)
            # függő postcheck lejárata (csak ACT módban írunk állapotot). A
            # recheck a lejárat után már `failed`-et ad, ez csak a biztosíték.
            if acting and st is not CORRUPT and st.get("pending_postcheck"):
                if now - st["pending_postcheck"]["restart_at"] > window_s(e):
                    st["pending_postcheck"] = None
                    save_state(e["agent"], st)
    # a gyors út (30 mp-es timer) csak akkor szól, ha tett valamit
    return {"mode": mode, "host": host, "lines": lines if acted or not fast else []}


def main() -> int:
    r = reconcile(observe="--observe" in sys.argv, fast="--fast" in sys.argv)
    for line in r["lines"]:
        print(line)
    if r["mode"] == "ACT" and "--fast" not in sys.argv:
        try:  # the capability tree, once a day; it never disturbs the reconcile
            from fleet import capabilities
            if capabilities.collect_if_due():
                print("képességfa: begyűjtve")
        except Exception as e:  # noqa: BLE001
            print("képességfa: a begyűjtés hibája (%s)" % type(e).__name__)
        try:  # 11-07: alapfunkció-próba ágensenként, jelentés a központi flotta-ellenőrzésnek
            from fleet import kepesseg_riaszt
            for line in kepesseg_riaszt.sweep():
                print(line)
        except Exception as e:  # noqa: BLE001
            print("képesség-próba: hiba (%s)" % type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
