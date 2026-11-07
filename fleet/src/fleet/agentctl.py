"""`fleet stop` / `fleet restart` — EGY ágens célzott leállítása és újraindítása.

Elfogadási mérés 2026-10-15: a leállítás-próbánál az ágens `pkill`-lel
próbálkozott, ami a közös tmux-szervert és a saját shelljét is leölte. Itt
csak az ágens unitja mozdul: a `systemctl --user stop` a unit ExecStop-ját
futtatja (`tmux kill-session -t =<session>`) — más session, más ágens,
a tmux-szerver érintetlen.

  stop             a felügyelet a reconcile-timer egy periódusán belül visszaindítja
                   (ez a próba; a periódust a telepített timerből olvassa)
  stop --hold N    karbantartási zár N percre: addig a reconcile nem indítja
  restart          zár feloldva, unit újraindítva, utána postcheck
"""
from __future__ import annotations
import re
import time
from pathlib import Path

from fleet import maintenance, requested_stop
from fleet.generation import _generation, clear_generation, mark_generation, read_generation  # noqa: F401
from fleet.postcheck import postcheck, format_postcheck
from fleet.txn import run_cmd


_DEFAULT_PERIOD_S = 300.0   # a régi sablon 5 perce, ha a timer nem olvasható
_UNITS = {"": 1, "s": 1, "sec": 1, "min": 60, "m": 60}


def _timer_period_s(name: str, home: Path | None) -> float | None:
    t = (home or Path.home()) / ".config" / "systemd" / "user" / name
    try:
        m = re.search(r"^OnUnitActiveSec=\s*(\d+)\s*([a-z]*)\s*$", t.read_text(), re.M)
    except OSError:
        return None
    return float(int(m.group(1)) * _UNITS[m.group(2)]) if m and m.group(2) in _UNITS else None


def reconcile_period_s(home: Path | None = None) -> float:
    """A telepített fleet-reconcile.timer `OnUnitActiveSec` periódusa másodpercben."""
    return _timer_period_s("fleet-reconcile.timer", home) or _DEFAULT_PERIOD_S


def return_bound_s(home: Path | None = None) -> float:
    """Meddig tarthat egy leölt processz visszajövetele. Gyors timerrel: két
    megfigyelés (megerősítés) + az indítás; nélküle a teljes kör periódusa."""
    fast = _timer_period_s("fleet-reconcile-fast.timer", home)
    return reconcile_period_s(home) if fast is None else 2 * fast + 10


def _fmt(sec: float) -> str:
    return f"{int(sec // 60)} perc" if sec >= 120 and sec % 60 == 0 else f"{int(sec)} mp"


def stop(entry: dict, *, hold_min: int | None = None, run=run_cmd, home: Path | None = None) -> dict:
    a, unit = entry["agent"], entry["unit"]
    notes = []
    if hold_min:
        p = maintenance.lock(a, hold_min)
        notes.append(f"karbantartási zár {hold_min} percre ({p}) — a reconcile addig nem indítja")
    mark_generation(a, _generation(entry))
    # kért leállás: a visszaindítás nem fogy a crash-loop költségvetésből
    requested_stop.mark(a, hold_min=hold_min)
    r = run(["systemctl", "--user", "stop", unit])
    if r.returncode != 0:
        requested_stop.clear(a)
        return {"ok": False, "notes": notes + [f"systemctl stop {unit}: kód {r.returncode} {r.stderr.strip()}"]}
    notes.append(f"leállítva: {unit} (csak a(z) {entry['session']} tmux-session)")
    notes.append(f"vissza: `fleet restart {a}`" if hold_min else
                 f"a fleet-reconcile ≤{_fmt(return_bound_s(home))} alatt visszaindítja "
                 f"(megvárni: `fleet wait-up {a}`); azonnal: `fleet restart {a}`")
    return {"ok": True, "notes": notes}


def restart(entry: dict, *, run=run_cmd, wait_s: int = 90, check=postcheck) -> dict:
    a, unit = entry["agent"], entry["unit"]
    maintenance.unlock(a)
    requested_stop.clear(a)     # itt indul, nem a reconcile: a jelölő ne mentsen fel egy későbbi összeomlást
    t0 = time.time()
    r = run(["systemctl", "--user", "restart", unit])
    if r.returncode != 0:
        return {"ok": False, "status": "failed",
                "notes": [f"systemctl restart {unit}: kód {r.returncode} {r.stderr.strip()}"]}
    pc = check(entry, restart_at=t0, wait_s=wait_s)
    return {"ok": pc["ok"], "status": pc["status"], "notes": [format_postcheck(pc)]}


def _proc_sig(entry: dict):
    from fleet import signals
    return signals.process_signal(entry)


def wait_up(entry: dict, *, timeout_s: float = 420, home: Path | None = None, sig=_proc_sig,
            sleep=time.sleep, clock=time.time, poll_s: float = 5) -> dict:
    """Megvárja, hogy az ágens ÚJ processz-generációja (más pid vagy indulási
    idő, mint a `stop` előtti) fusson, és megmondja mikor várható. A leállás
    közben még látszó régi processz NEM visszajövetel (06-flotta, 2. kör).
    Zár alatt vagy dormant ágensnél nem vár: ott nem is jön vissza."""
    from fleet.registry import is_dormant
    a = entry["agent"]
    if is_dormant(entry):
        return {"ok": False, "notes": [f"{a}: dormant — nem jön vissza (a registryben pihen)"]}
    if maintenance.is_locked(a):
        return {"ok": False, "notes": [f"{a}: karbantartási zár alatt — nem jön vissza, amíg le nem jár; "
                                       f"azonnal: `fleet restart {a}`"]}
    period = return_bound_s(home)
    mark = read_generation(a)
    t0 = clock()
    notes = [f"{a}: várható visszajövetel ≤{_fmt(period)} (a felügyelet timere), várok legfeljebb {_fmt(timeout_s)}"]
    first, seen_down = True, False
    while True:
        s = sig(entry)
        if s.state == "up":
            gen = {"pid": s.data.get("pid"), "started_s": s.data.get("started_s")}
            if mark is None and first:
                notes.append(f"{a}: már fut (pid {gen['pid']}) — nincs mire várni (előtte nem volt `fleet stop`)")
                return {"ok": True, "notes": notes}
            if (mark is None and seen_down) or (mark is not None and gen != mark):
                clear_generation(a)
                notes.append(f"{a}: új processz fut (pid {gen['pid']}), visszajött {int(clock() - t0)} mp alatt")
                return {"ok": True, "notes": notes}
        else:
            seen_down = True
        first = False
        if clock() - t0 >= timeout_s:
            old = " (még a régi processz látszik)" if mark is not None and s.state == "up" else ""
            notes.append(f"{a}: NEM jött vissza {int(clock() - t0)} mp alatt{old} — `fleet doctor {a}`, "
                         f"a reconcile naplója: `journalctl --user -u fleet-reconcile -n 20`")
            return {"ok": False, "notes": notes}
        sleep(poll_s)
