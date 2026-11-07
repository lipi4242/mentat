"""`fleet setup <ágens>` — a kihelyezés EGY parancsa, azon a boxon, ahova az
ágens kerül. A lánc (mindegyik lépés a meglévő parancs, nem másolat):

  registry → validate → join → preflight → install (tmux, auth a unit
  szemével, első indítás ablakai, session-id hook, unit, felügyelet,
  postcheck, pane-ellenőrzés) → híd → plugin → első tick (ha a flotta
  ütemez) → reconcile → doctor  →  egy összefoglaló sor

Idempotens: újrafuttatva csak a hiányzót pótolja. `--check`: semmit nem ír,
csak megmondja, mi hiányzik. Kilépési kód: 0 kész (doctor: healthy) ·
3 fut, de még nem dőlt el (pending) · 1 hiba (a sor megmondja, mi a teendő).
"""
from __future__ import annotations
import os
import time
from pathlib import Path

from fleet import claude_auth, claude_firstrun, registry_dir, tick_watch
from fleet import registry as reg
from fleet.install_checks import CLAUDE_BIN, TMUX_BIN, tmux_problem
from fleet.txn import run_cmd

STEP_ORDER = ("validate", "join", "preflight", "install", "bridge", "plugin", "tick", "reconcile", "doctor")


def _fail(res: dict, step: str, problems: list[str]) -> dict:
    res["steps"].append((step, "HIBA", problems))
    res["status"] = "failed"
    res["summary"] = f"fleet setup {res['agent']}: NEM KÉSZ ({step}) — {problems[0]}"
    return res


def _own(agent: str, problems: list[str]) -> list[str]:
    """A validate problémái közül, ami ezt az ágenst (vagy a registry egészét) érinti."""
    names = [e["agent"] for e in reg.load_agents()]
    return [p for p in problems if p.startswith(f"{agent}:")
            or not any(p.startswith(f"{n}:") for n in names)]


def setup(agent: str, *, check: bool = False, first_tick: bool = True, home: Path | None = None,
          claude_bin: Path = CLAUDE_BIN, run=run_cmd, fix_claude_md: bool = False,
          tmux_bin: Path = TMUX_BIN, plugin_source: str | None = None) -> dict:
    from fleet.validate import validate
    from fleet.preflight import preflight
    home = home or Path.home()
    res = {"agent": agent, "steps": [], "status": "failed", "summary": ""}
    entry = reg.get_agent(agent)
    if entry is None:
        return _fail(res, "registry", [f"nincs ilyen ágens a registryben ({registry_dir()}): {agent}"])
    n, problems = validate(registry_dir())
    own = _own(agent, problems)
    if own:
        return _fail(res, "validate", own)
    res["steps"].append(("validate", "ok", [f"{n} ágens; más ágensek hibái: {len(problems)}"] if problems else []))
    repo = tick_watch.workdir(entry, home)
    if not (repo / ".git").exists():
        return _fail(res, "join", [f"a workdir nem git repó: {repo}"])
    if check:
        res["steps"].append(("join", "check", ["(nem írok)"]))
    else:
        from fleet.join import join
        res["steps"].append(("join", "ok", join(repo, agent=agent, fix_claude_md=fix_claude_md,
                                                  plugin_source=plugin_source)["notes"]))
    findings = preflight(entry, home=home) + ([] if reg.is_dormant(entry) else tmux_problem(tmux_bin))
    if findings:
        return _fail(res, "preflight", findings)
    res["steps"].append(("preflight", "ok", []))
    if check:
        return _check_install(res, entry, home, claude_bin)
    return _deploy(res, entry, home, claude_bin, run, first_tick, tmux_bin, plugin_source)


def _check_install(res: dict, entry: dict, home: Path, claude_bin: Path) -> dict:
    problems, notes = [], []
    if not claude_auth.logged_in(entry, claude_bin=claude_bin, home=home):
        if os.environ.get(claude_auth.TOKEN_VAR):
            notes.append(f"átadnám a unitnak a shell {claude_auth.TOKEN_VAR}-jét (0600)")
        else:
            problems.append(f"a unit nem lát logint, és ebben a shellben nincs {claude_auth.TOKEN_VAR} — "
                            f"`fleet auth {entry['agent']}` (ahol a claude be van jelentkezve) vagy `claude auth login`")
    fr = claude_firstrun.apply(entry, home=home, check=True)
    res["steps"].append(("install", "check", problems + fr["problems"] + notes +
                         [f"beállítanám: {c}" for c in fr["changes"]]))
    res["status"] = "failed" if problems or fr["problems"] else "ok"
    res["summary"] = (f"fleet setup {entry['agent']} --check: "
                      + ("telepíthető" if res["status"] == "ok" else f"{len(problems + fr['problems'])} akadály"))
    return res


def _deploy(res: dict, entry: dict, home: Path, claude_bin: Path, run, first_tick: bool,
            tmux_bin: Path, plugin_source: str | None = None) -> dict:
    from fleet.install_flow import install_agent
    from fleet.plugin_install import install_plugin
    from fleet.reconcile import reconcile
    from fleet.doctor import doctor
    a = entry["agent"]
    r = install_agent(entry, home=home, claude_bin=claude_bin, tmux_bin=tmux_bin)
    if r["status"] == "failed":
        return _fail(res, "install", r["problems"] + [f"journal: {x}" for x in r["journal"][-5:]])
    res["steps"].append(("install", r["status"], r["notes"]))
    bunit = (entry.get("bridge") or {}).get("unit")
    if bunit and not reg.is_dormant(entry):
        from fleet.bridge import install_bridge
        b = install_bridge(entry)
        rr = run(["systemctl", "--user", "restart", bunit])
        res["steps"].append(("bridge", "ok" if rr.returncode == 0 else "HIBA", [f"{bunit} {b['version']}"]))
    p = install_plugin(entry, claude_bin=claude_bin, home=home, plugin_source=plugin_source)
    from fleet import titok_telepit   # H5: minden Claude-gyökérbe, a fogadóéba is
    res["steps"].append(("plugin", "ok" if p["ok"] else "figyelem", [p["note"]]))
    try:
        res["steps"].append(("titok-kapu", "ok", titok_telepit.install(home)))
    except titok_telepit.SelfTestFailed as e:  # hangos, de a setup többi lépése megy tovább
        res["steps"].append(("titok-kapu", "HIBA", [str(e)]))
    ft = tick_watch.fleet_tick(entry, home, time.time())
    if ft is not None and ft["tick_age"] is None and first_tick:
        # a flotta timere csak a következő egész órában tickelne; egy tick most
        # bizonyítja, hogy az ütemezés él (`--no-tick`: kihagyja)
        t = run(["systemctl", "--user", "start", f"fleet-tick-{a}.service"])
        res["steps"].append(("tick", "ok" if t.returncode == 0 else "HIBA",
                             [f"első tick: fleet-tick-{a}.service → kód {t.returncode}"]))
    res["steps"].append(("reconcile", "ok", reconcile(only=a)["lines"]))
    d = [x for x in doctor(agent=a) if x["agent"] == a]
    health = d[0]["health"] if d else "unknown"
    sig = d[0].get("signals", {}) if d else {}
    res["steps"].append(("doctor", health, (d[0]["problems"] + d[0]["pending"] + d[0]["unknown"]) if d else []))
    res["status"] = {"healthy": "ok", "pending": "pending"}.get(health, "failed")
    head = {"ok": "KÉSZ", "pending": "FUT, MÉG NEM DŐLT EL"}.get(res["status"], "NEM KÉSZ")
    res["summary"] = (f"fleet setup {a}: {head} — doctor: {health} · "
                      + " · ".join(f"{k} {v['state']}" for k, v in sig.items())
                      + f" · {p['note'].split(' — ')[0]}")
    return res


def format_setup(res: dict) -> str:
    out = []
    for step, state, notes in res["steps"]:
        out.append(f"  [{state}] {step}")
        out += [f"      {n}" for n in notes]
    return "\n".join(out + [res["summary"]])
