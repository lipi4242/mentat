"""A tick-kapu systemd user unitjai a registryből: `fleet-gate-<ágens>.{service,timer}`.

Tiszta render + egy tranzakciós telepítő (a `fleet install` ugyanabban a Txn-ben hívja, és
`fleet tick-gate install <ágens>` külön is). A service oneshot, `Nice=10`, 30 s-os
TimeoutStartSec — az előellenőrzés célja ≤ 5 s; egy beragadt hívás se tartsa a következő
tüzelést. `Persistent=false`: egy hosszú leállás után NEM jön tüzelés-zápor.
"""
from __future__ import annotations

from pathlib import Path

from fleet import tick_gate as tg
from fleet.tick_gate_health import gate_unit
from fleet.txn import Txn


def render(entry: dict, fleet_root: str) -> dict[str, str]:
    cfg = tg.config(entry)
    if cfg is None:
        return {}
    bad = tg.problems(cfg)
    if bad:
        raise ValueError("tick_gate nem renderelhető: " + "; ".join(bad))
    a, u = entry["agent"], gate_unit(entry["agent"])
    service = (f"# Mentat fleet: tick-kapu ({a}) — LLM nélküli előellenőrzés, csak munka esetén tick.\n"
               f"# Ne szerkeszd: `fleet tick-gate install {a}` / `fleet install {a}` írja.\n"
               f"[Unit]\nDescription=tick-kapu ({a})\n\n[Service]\nType=oneshot\nNice=10\nTimeoutStartSec=30\n"
               f"WorkingDirectory={fleet_root}\n"
               f"Environment=PATH=%h/.bun/bin:%h/.local/bin:/usr/local/bin:/usr/bin:/bin\n"
               f"ExecStart={fleet_root}/bin/fleet tick-gate run {a}\n")
    timer = (f"[Unit]\nDescription=tick-kapu ütem ({a}, {cfg['preset']})\n\n[Timer]\n"
             + "\n".join(tg.calendars(cfg))
             + f"\nPersistent=false\nAccuracySec=30s\nUnit={u}.service\n\n[Install]\nWantedBy=timers.target\n")
    return {f"{u}.service": service, f"{u}.timer": timer}


def install(t: Txn, entry: dict, unit_dir: Path, fleet_root: str) -> list[str]:
    """Írás + daemon-reload + enable --now; bukásnál a hívó Txn-je állít vissza. Kapu nélkül no-op."""
    files = render(entry, fleet_root)
    if not files:
        return []
    notes = []
    for name, text in files.items():
        if t.write(Path(unit_dir) / name, text):
            notes.append(f"tick-kapu: {name} írva")
    timer = f"{gate_unit(entry['agent'])}.timer"
    t.sh(["systemctl", "--user", "daemon-reload"])
    was = t.try_sh(["systemctl", "--user", "is-active", timer]).stdout.strip() == "active"
    t.sh(["systemctl", "--user", "enable", "--now", timer],
         undo=None if was else ["systemctl", "--user", "disable", "--now", timer])
    if not was:
        notes.append(f"tick-kapu: {timer} élesítve")
    return notes
