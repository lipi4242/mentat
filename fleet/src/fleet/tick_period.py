"""A registry `tick_period_s`-e a flotta tick-timerében (H5-3, 2026-10-29: az órás tick a 8:30-at sosem érte el,
és a `tick_period_s` csak az egészségfigyelést állította, az ütemet nem).

`calendar(period)` → OnCalendar-érték; `apply(agent, period)` a `fleet-tick-<ágens>.timer`-t TELJES szöveggel
újraírja (tick_schedule.timer_text — a flotta a saját fájlját írja; regex-csere egy eltérő fájlból OnCalendar
nélküli, soha nem tüzelő timert csinálhat, CISO Q4), visszaolvasva ellenőrzi az OnCalendar-sort, majd
daemon-reload és restart; bármelyik hibája ValueError. Ha nincs ilyen timer ezen a gépen, jelzi.
"""
from __future__ import annotations
import subprocess
from pathlib import Path


def calendar(period: int) -> str:
    """Az óra/nap egészével osztható periódus systemd OnCalendar-alakja; különben ValueError."""
    if period < 300:
        raise ValueError("legalább 300 mp")
    if period < 3600 and 3600 % period == 0 and period % 60 == 0:
        return f"*:00/{period // 60}"
    if period == 3600:
        return "hourly"
    if period % 3600 == 0 and 86400 % period == 0:
        return f"00/{period // 3600}:00"
    raise ValueError("a periódus osszon maradék nélkül egy órát vagy egy napot (pl. 900, 1800, 3600, 7200)")


def apply(agent: str, period: int, unit_dir: Path | None = None, run=subprocess.run) -> str:
    from fleet.install import UNIT_DIR
    from fleet.tick_schedule import tick_unit, timer_text
    cal = calendar(period)
    timer = Path(unit_dir or UNIT_DIR) / f"{tick_unit(agent)}.timer"
    if not timer.is_file():
        return f"ütem: nincs {timer.name} ezen a gépen — a boxon futtasd, vagy `fleet join` után"
    timer.write_text(timer_text(agent, [f"OnCalendar={cal}"]))
    if f"OnCalendar={cal}" not in timer.read_text().splitlines():
        raise ValueError(f"{timer.name}: az OnCalendar-sor nincs a fájlban az írás után")
    for cmd in (["daemon-reload"], ["restart", timer.name]):
        r = run(["systemctl", "--user", *cmd], check=False, capture_output=True, text=True)
        if r.returncode:
            raise ValueError(f"systemctl --user {' '.join(cmd)}: kód {r.returncode} "
                             f"({(r.stderr or '').strip()[-200:]})")
    return f"ütem: {timer.name} OnCalendar={cal}"
