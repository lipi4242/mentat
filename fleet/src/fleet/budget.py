"""A restart-keret kimerülése egy sorban — doctor, status és a session-indítás.

2. kör, 06-flotta: a keret 10:07-kor elfogyott, és ezt csak a reconcile
journalja mondta ki; a doctor közben "healthy"-t mutatott. Ez a modul nem dönt
(a döntés a reconcile.decide-é), csak kimondja: kimerült-e, és mikor szabadul.

  python3 -m fleet.budget <ágens>   → egy sor, ha kimerült; különben semmi; mindig 0
"""
from __future__ import annotations
import sys
import time

from fleet.reconcile import BUDGET_WINDOW_S, CORRUPT, RESTART_BUDGET, budget_left, load_state


def exhausted_line(st, now: float | None = None) -> str | None:
    """Egy sor, ha a crash-restart keret (a kért leállás utániak nélkül) kimerült."""
    now = time.time() if now is None else now
    if st is CORRUPT or not isinstance(st, dict) or budget_left(st, now) > 0:
        return None
    recent = sorted(t for t in st.get("restarts", []) if now - t < BUDGET_WINDOW_S)
    free_at = recent[-RESTART_BUDGET] + BUDGET_WINDOW_S    # ekkor lesz újra egy szabad hely
    mins = max(1, int((free_at - now) // 60))
    hhmm = time.strftime("%H:%M", time.localtime(free_at))
    return (f"restart-keret kimerült ({RESTART_BUDGET}/óra): a következő leállás után a felügyelet "
            f"NEM indítja újra; felszabadul {hhmm}-kor ({mins} perc múlva) · kézzel: `fleet restart`")


def line_for(agent: str, now: float | None = None) -> str | None:
    return exhausted_line(load_state(agent), now)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        line = line_for(args[0]) if args else None
    except Exception:       # a session-indítást semmi nem akaszthatja meg
        line = None
    if line:
        print(f"[fleet] {args[0]}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
