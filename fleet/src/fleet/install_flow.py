"""`fleet install <ágens>` — tranzakciós telepítés zöld postcheckig.

Sorrend: host-egyezés, tmux, claude-bináris + login a unit szemével →
az első indítás ablakai előre elfogadva + session-id hook (claude_firstrun) →
unit, drop-in, felügyelet (egy tranzakcióban) → indítás → a processz
megmarad-e, és NEM áll-e dialógusnál a pane → postcheck. A „kész"
csak zöld postcheckkel jár. Ha a claude azonnal kilép (auth, kredit, hiányzó
bináris), a telepítés érthető hibával áll meg a unit journaljának utolsó
soraival, és visszaáll az előző állapot.

Eredmény: `ok` (kész) · `pending` (fut, de a postcheck még nem dőlt el — a
reconcile viszi tovább) · `failed` (visszaállítva).
"""
from __future__ import annotations
import time
from pathlib import Path

from fleet import CONFIG_DIR, claude_auth, claude_firstrun, pane, registry_dir, signals
from fleet.install import UNIT_DIR, fleet_root_for_units, install_unit
from fleet.postcheck import postcheck, OK, PENDING
from fleet.registry import is_dormant, local_host
from fleet.supervision import ensure_supervision
from fleet.install_checks import CLAUDE_BIN, TMUX_BIN, claude_says, journal_tail, precheck
from fleet.txn import Txn, StepFailed, run_cmd

def _is_new(p: dict, since: float | None) -> bool:
    """Az újraindítás UTÁN indult-e a processz. A régi claude a tmux kill-session
    után még egy-két másodpercig él (KillMode=none), és ha az első mérés még őt
    látja, a 15 s-os stabilitás-próba pid-cserét lát — 11-07-én így bukott egy
    éles ágens telepítése, pedig az új processz végig futott."""
    started = (p.get("data") or {}).get("started_s")
    return since is None or started is None or started >= since - 2


def _stays_up(entry: dict, *, measure, sleep, wait_s: float, stable_s: float, poll_s: float = 2.0,
              since: float | None = None):
    """(pid vagy None). Megvárja, hogy az újraindítás utáni processz feljöjjön,
    aztán hogy `stable_s` múlva is UGYANAZ fusson — az azonnal kilépő claude-ot
    ez fogja meg. A `since` előtt indult (haldokló régi) processzt nem számolja."""
    waited = 0.0
    while True:
        p = measure(entry)["signals"]["process"]
        if p["state"] == "up" and _is_new(p, since):
            break
        if waited >= wait_s:
            return None
        sleep(poll_s); waited += poll_s
    pid = p["data"].get("pid")
    sleep(stable_s)
    p2 = measure(entry)["signals"]["process"]
    return pid if p2["state"] == "up" and p2["data"].get("pid") == pid else None


def install_agent(entry: dict, *, unit_dir: Path = UNIT_DIR, config_dir: Path = CONFIG_DIR,
                  registry: Path | None = None, host: str | None = None, run=run_cmd,
                  claude_bin: Path = CLAUDE_BIN, measure=signals.measure, postcheck_fn=postcheck,
                  sleep=time.sleep, wait_s: float = 60, stable_s: float = 15,
                  record_pending=None, now=time.time, home: Path | None = None,
                  tmux_bin: Path = TMUX_BIN, run_env=claude_auth.run_env, environ=None,
                  pane_fn=None) -> dict:
    a = entry["agent"]; unit = entry["unit"]
    home = home or Path.home()
    res = {"agent": a, "status": "failed", "notes": [], "problems": [], "journal": []}
    host = host if host is not None else local_host()
    res["problems"] = precheck(entry, host=host, claude_bin=claude_bin, run=run, home=home,
                               warnings=res["notes"], tmux_bin=tmux_bin, run_env=run_env,
                               environ=environ)
    if res["problems"]:
        return res
    if not is_dormant(entry):
        fr = claude_firstrun.apply(entry, home=home)
        res["notes"] += [f"első indítás előre beállítva: {c}" for c in fr["changes"]]
        if fr["problems"]:
            res["problems"] += fr["problems"]
            return res
    pane_fn = pane_fn or (lambda session: pane.pane_dialog(session, run, str(tmux_bin)))
    t = Txn(run)
    was_active = run(["systemctl", "--user", "is-active", unit]).stdout.strip() == "active"
    did_restart = False   # csak akkor indítjuk újra a régit, ha mi állítottuk le
    try:
        r = install_unit(entry, unit_dir=unit_dir, txn=t, config_dir=Path(config_dir))
        res["notes"] += ensure_supervision(t, unit_dir=Path(unit_dir), config_dir=Path(config_dir),
                                           fleet_root=fleet_root_for_units(),
                                           registry=registry or registry_dir())
        if is_dormant(entry):
            res["status"] = OK
            res["notes"].append("dormant: telepítve, nem indítva (a reconcile tartja leállítva)")
            return res
        started = now()
        restarted = r["changed"] or not was_active
        if restarted:
            did_restart = True
            t.sh(["systemctl", "--user", "restart", unit])
        if _stays_up(entry, measure=measure, sleep=sleep, wait_s=wait_s, stable_s=stable_s,
                     since=started if restarted else None) is None:
            raise StepFailed("a claude elindult, de azonnal kilépett, vagy fel sem jött "
                             "(auth, kredit, hiányzó bináris?) — a journal utolsó sorai lent")
        stuck = pane_fn(entry["session"])
        if stuck:   # a unit `active`, a processz fut — és mégsem dolgozik
            raise StepFailed(stuck)
        pc = postcheck_fn(entry, restart_at=started if restarted else None, wait_s=0)
        if pc["status"] == OK:
            res["status"] = OK
            res["notes"].append("postcheck OK — kész")
            return res
        if pc["status"] == PENDING:
            res["status"] = PENDING
            res["notes"] += [f"még nem dőlt el: {x}" for x in pc["pending"]]
            (record_pending or _record_pending)(a, started)
            return res
        raise StepFailed("postcheck HIBA: " + "; ".join(pc["problems"]))
    except (StepFailed, OSError, ValueError) as e:
        res["problems"].append(str(e))
        res["journal"] = journal_tail(unit, run)
        if not claude_auth.logged_in(entry, claude_bin=claude_bin, home=home, run=run_env):
            res["problems"].append(f"a claude a unit számára nincs bejelentkezve (`fleet auth {a}`)")
        res["journal"] += claude_says(entry, claude_bin, run)
        res["notes"] += t.rollback()
        if was_active and not did_restart:
            # 11-07: egy hiányzó kézi unit-forrás (még írás előtt) a futó ágenst
            # feleslegesen újraindította, ~70 s híd nélkül. A régi processz itt
            # érintetlen; a visszaállított fájlokhoz elég a daemon-reload.
            run(["systemctl", "--user", "daemon-reload"])
            res["notes"].append("semmi nem indult újra: a futó ágens érintetlen")
        elif was_active:
            back = run(["systemctl", "--user", "restart", unit])
            res["notes"].append("az előző unit visszaállítva és újraindítva"
                                if back.returncode == 0 else
                                f"az előző unit visszaállítva, de az újraindítás bukott (kód {back.returncode})")
        else:
            run(["systemctl", "--user", "stop", unit])
            res["notes"].append("visszaállítva: az ágens nem fut (előtte sem futott)")
        return res


def _record_pending(agent: str, started: float) -> None:
    """A reconcile minden periódusban újranézi, és a türelmi idő végén ítél."""
    from fleet.reconcile import load_state, save_state, CORRUPT
    st = load_state(agent)
    if st is not CORRUPT:
        st["pending_postcheck"] = {"restart_at": started}
        save_state(agent, st)


def format_install(r: dict) -> str:
    head = {"ok": "KÉSZ", "pending": "TELEPÍTVE, DE MÉG NEM KÉSZ", "failed": "NEM SIKERÜLT"}[r["status"]]
    out = [f"fleet install {r['agent']}: {head}"]
    out += [f"  - {n}" for n in r["notes"]]
    out += [f"  ! {p}" for p in r["problems"]]
    if r["journal"]:
        out.append("  journal (utolsó sorok):")
        out += [f"    {line}" for line in r["journal"]]
    if r["status"] == "pending":
        out.append("  a reconcile minden periódusban újranézi; `fleet doctor <ágens>` mutatja, hol tart")
    return "\n".join(out)
