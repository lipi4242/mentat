"""`fleet doctor` — a négy jel emberi olvasatban, plusz a telepítési tények:
unit engedélyezve/aktív, drop-in megvan-e, híd-verzió, Claude-fiók, és a fail-open
hookok (F-39: onFailure:"block" hiányzik, vagy a Claude Code régebbi 2.1.295-nél) — csak jelzés —,
és hogy a futó claude env-jében van-e felügyelet nélküli jel a nemakad hooknak (envjel.py).
Essentials (11-07, essentials.py): a telepített titok-kapu tiltja-e az ágens alapfunkcióit
(Telegram-küldés, todo, git, saját állapot), van-e TELEGRAM_BOT_TOKEN (név szerint) a hidas ágens
unitjának env-jében, és futott-e a send.mjs token nélkül — piros; a leltárfájlt `.`-tal töltő
ágens-szkript teendő (⚠). PROXY-jel (paneor.py): a unit claude binárisában megvannak-e a híd pane-őrének mintái (F-17).
Box-sor (11-07, doctor_box.py, csak ágens-név nélkül): a független riasztási út és a
kézbesítetlen riasztások, a felhasználói hookok/pluginok kanári nélküli változása, kiadás-lemaradás.
`--fix` = reconcile egy ágensre, végrehajtással (ez az operátor kifejezett
parancsa, ezért nem vár a controller-fájlra).

Igazmondás: `ok` csak akkor igaz, ha az összesített egészség
`healthy` (health.py) — a `pending` és az `unknown` nem OK. Kivétel az
opcionális RC: nem mérhetően `n/a`, és nem rontja a kilépési kódot. Egy
indítási ablaknál álló pane (pane.py) hiba, akkor is, ha a processz fut. A `--fix` sikere
NEM a reconcile lefutása, hanem a javítás UTÁNI újramérés: csak ha az is
`healthy`.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

from fleet import dup, signals, maintenance, pane, hookguard, envjel, paneor, outward_hold_box
from fleet.health import HEALTHY, UNHEALTHY, UNKNOWN_H, MARK, judge, worst
from fleet.registry import load_agents, agents_for_host, local_host, is_dormant
from fleet.bridge import read_stamp, bridge_version
from fleet.install import UNIT_DIR
from fleet.reconcile import load_state, decide, reconcile


def _report(agent: str, facts: list, problems: list, s: dict, j: dict | None = None,
            warnings: list | None = None) -> dict:
    """Az összesítés: a jelek ítélete és a nem-jel problémák közül a legrosszabb.
    A `warnings` teendő, nem üzemzavar (híd verzió-drift): az ágens
    dolgozik, ezért nem rontja az egészséget — külön sorban látszik (⚠️)."""
    j = j or {"health": HEALTHY, "pending": [], "unknown": [], "unhealthy": []}
    health = worst([j["health"]] + ([UNHEALTHY] if problems else []))
    return {"agent": agent, "ok": health == HEALTHY, "health": health, "facts": facts,
            "problems": j["unhealthy"] + problems, "warnings": list(warnings or []),
            "pending": j["pending"], "unknown": j["unknown"], "signals": s}


def _workdir(entry: dict) -> Path:
    """The agent repo: the unit's WorkingDirectory, %h = this user's HOME."""
    return Path(str(entry.get("workdir") or "").replace("%h", str(Path.home())))


def _sysctl_prop(unit: str, prop: str) -> str | None:
    try:
        r = subprocess.run(["systemctl", "--user", "show", "-p", prop, "--value", unit],
                           capture_output=True, text=True)
        return r.stdout.strip() or None
    except OSError:
        return None


def assess(entry: dict, m: dict, st: dict, *, unit_active: str | None,
           unit_enabled: str | None, drop_in: bool, bridge_installed: str | None,
           bridge_current: str, locked: bool, pane_dialog: str | None = None,
           now: float | None = None, hook_problems: list[str] = (),
           claude_problem: str | None = None, claude_unknown: str | None = None,
           env_check: tuple = (None, None), outward: dict | None = None,
           bridge_stale: str | None = None, essentials: dict | None = None) -> dict:
    """Pure: egészség (health.py) + a tények listája. A híd verzió-driftje teendő
    (`warnings`), nem üzemzavar; a fail-open hook (F-39) szándékosan piros."""
    facts = []
    problems = []
    warnings = []
    s = m["signals"]
    if is_dormant(entry):
        running = s["process"]["state"] == "up" or unit_active == "active"
        if running:
            problems.append("dormant, de fut")
        facts.append(f"kívánt: dormant · unit {unit_active}/{unit_enabled}")
        return _report(entry["agent"], facts, problems, s)
    facts.append(f"kívánt: active · unit {unit_active}/{unit_enabled} · fiók {entry.get('claude_account')}")
    j = judge(s)
    for k, v in s.items():
        facts.append(f"{k:9} {v['state']:13} {j['per_signal'][k][0]:9} {v['detail']}")
    if pane_dialog:
        problems.append(pane_dialog)
    problems += list(hook_problems) + ([claude_problem] if claude_problem else [])  # F-39, jelzés
    if env_check[0]:
        problems.append(env_check[0])  # nemakad: nincs felügyelet nélküli jel
    if m["pollers"]:
        problems.append(f"telegram-plugin poller: {m['pollers']}")
    if not drop_in:
        problems.append("hiányzik a session-gate drop-in")
    if entry.get("bridge", {}).get("unit"):
        facts.append(f"híd: telepítve {bridge_installed or '-'} · repó {bridge_current}")
        if bridge_stale:
            problems.append(bridge_stale)
        if bridge_installed != bridge_current:
            warnings.append(f"híd-drift: {bridge_installed} ≠ {bridge_current} (`fleet bridge install {entry['agent']}`)")
    ess = essentials or {}
    problems += list(ess.get("red", []))  # 11-07: tiltott alapfunkció / token nélküli unit / néma küldés
    facts += list(ess.get("facts", []))  # 11-07: ami a képesség-próbán ténylegesen lefutott
    warnings += list(ess.get("warn", []))
    if st.get("quarantined"):
        problems.append("KARANTÉN — ember oldja fel")
    from fleet.budget import exhausted_line
    over = exhausted_line(st, now)
    if over:
        problems.append(over)
    if locked:
        facts.append("karbantartási zár aktív")
    if outward and (outward.get("active") or outward.get("present")):
        from fleet.outward_hold import line
        facts.append(line(outward))   # tény, nem hiba: a tartás szándékos (a tick ezalatt nem bélyegez)
    rss = s["process"]["data"].get("rss_mb")
    if rss:
        facts.append(f"memória: {rss} MB")
    rep = _report(entry["agent"], facts, problems, s, j, warnings)
    for unk in [claude_unknown, env_check[1]] + list(ess.get("unknown", [])):  # N2: not measurable is not green
        if not unk:
            continue
        rep["unknown"] = rep["unknown"] + [unk]
        rep["health"] = worst([rep["health"], UNKNOWN_H])
        rep["ok"] = rep["health"] == HEALTHY
    return rep


def _bridge_stale(entry: dict) -> str | None:
    unit = (entry.get("bridge") or {}).get("unit")
    if not unit:
        return None
    from fleet import bridge_fresh
    return bridge_fresh.problem(unit, Path.home() / ".config" / entry["agent"] / "sub-etha",
                                signals._proc_records())


def hook_problems_for(entry: dict) -> list[str]:
    """F-39: the agent repo's hooks and its Claude home's user-level hooks (N1)."""
    home = signals.claude_home(entry)
    return (hookguard.hook_problems(_workdir(entry)) + hookguard.user_hook_problems(home)
            + hookguard.secrets_gate_problems(home))


def essentials_for(entry: dict) -> dict:
    """11-07: az ágens alapfunkciói a TELEPÍTETT titok-kapun (ha él) + a futásidejű előfeltételek."""
    from fleet import essentials, essentials_env, titok_telepit
    home = Path.home()
    live = (titok_telepit.code_dir(home) / "current" / "titok_kapu.py").is_file()
    r = essentials.probe([entry], home, gate=live).get(entry["agent"]) or {"red": [], "warn": [], "unknown": []}
    sent = essentials_env.send_failures(entry, home)
    from fleet import kepesseg  # 11-07: és le is fut-e (küldés dry-run, todo, állapot, git)
    cap = kepesseg.check(entry, home)
    return {**r, "red": r["red"] + ([sent] if sent else []) + cap["red"],
            "unknown": r["unknown"] + cap["unknown"], "facts": [kepesseg.summary(cap)] if cap["ok"] else []}


def doctor(agent: str | None = None, fix: bool = False) -> list[dict]:
    host = local_host()
    out = []
    agents = load_agents()
    # Más gépre rendelt ágens, ami itt fut — külön, hangos sor
    for fe, pid in dup.foreign_here(agents, host, signals._proc_records()):
        if not agent or fe["agent"] == agent:
            out.append(_report(fe["agent"], [f"registry host: {fe['host']} · ez a gép: {host}"],
                               [dup.dup_message(fe, pid, host)], {}))
    ver = hookguard.claude_version()
    claude_problem, claude_unknown = hookguard.version_problem(ver), hookguard.version_unknown(ver)
    pane_proxy = [x for x in [paneor.problem(hookguard.CLAUDE_BIN)] if x]  # F-17, gépenként egyszer
    for e in agents_for_host(host, agents):
        if agent and e["agent"] != agent:
            continue
        if e.get("supervision") == "none":
            out.append(_report(e["agent"], ["supervision=none — nem felügyelt, nem mérjük"], [], {}))
            continue
        m = signals.measure(e)
        st = load_state(e["agent"])
        drop_in = (Path(UNIT_DIR) / f"{e['unit']}.d" / "10-session-gate.conf").exists()
        rep = assess(e, m, st,
                     unit_active=_sysctl_prop(e["unit"], "ActiveState"),
                     unit_enabled=_sysctl_prop(e["unit"], "UnitFileState"),
                     drop_in=drop_in,
                     bridge_installed=read_stamp(Path.home() / ".config" / e["agent"] / "sub-etha" / "bridge.mjs"),
                     bridge_current=bridge_version(),
                     locked=maintenance.is_locked(e["agent"]),
                     pane_dialog=pane.pane_dialog(e["session"])
                     if m["signals"]["process"]["state"] == "up" else None,
                     hook_problems=hook_problems_for(e) + pane_proxy,
                     claude_problem=claude_problem, claude_unknown=claude_unknown,
                     env_check=envjel.check(m["signals"]["process"]["data"].get("pid"))
                     if m["signals"]["process"]["state"] == "up" else (None, None),
                     outward=outward_hold_box.read(_workdir(e)) if e.get("workdir") else None,
                     bridge_stale=_bridge_stale(e), essentials=essentials_for(e))
        out.append(rep)
    if agent is None:  # 11-07: a box-sor — riasztási út, kanári-lenyomat, kiadás-lemaradás
        from fleet import doctor_box
        out.append(doctor_box.box_facts(Path.home(), host))
    if fix and agent:
        from fleet import reconcile as rc
        # kifejezett operátori parancs: a controller-fájltól függetlenül hajt végre
        orig = rc.controller_is_us
        rc.controller_is_us = lambda: True
        try:
            r = reconcile(only=agent)
        finally:
            rc.controller_is_us = orig
        out.append(_after_fix(agent, r["lines"]))
    return out


def _after_fix(agent: str, lines: list[str]) -> dict:
    """A javítás eredménye = újramérés a javítás UTÁN. A reconcile lefutása
    nem bizonyíték (2026-10-14-ig itt feltétel nélküli `ok: True` állt)."""
    again = [r for r in doctor(agent=agent) if r["agent"] == agent]
    if not again:
        return _report(agent, ["--fix: " + x for x in lines],
                       ["a javítás után az ágens nem mérhető újra (nincs ezen a hoston?)"], {})
    r = again[0]
    verdict = "SIKER" if r["ok"] else f"NEM SIKERÜLT — újramérve: {r['health']}"
    r = dict(r, facts=[f"--fix: {x}" for x in lines] + [f"--fix eredménye: {verdict}"] + r["facts"])
    return r


def format_report(reports: list[dict]) -> str:
    lines = []
    for r in reports:
        health = r.get("health", HEALTHY if r["ok"] else UNHEALTHY)
        warn = r.get("warnings", [])
        mark = "⚠️" if health == HEALTHY and warn else MARK[health]
        lines.append(f"{mark} {r['agent']} — {health}" + (f" · {len(warn)} teendő" if warn else ""))
        for f in r["facts"]:
            lines.append(f"     {f}")
        for p in r["problems"]:
            lines.append(f"   ! {p}")
        for p in r.get("warnings", []):
            lines.append(f"   ⚠ {p}")
        for p in r.get("pending", []):
            lines.append(f"   … még nem dőlt el: {p}")
        for p in r.get("unknown", []):
            lines.append(f"   ? nem mérhető: {p}")
    return "\n".join(lines)
