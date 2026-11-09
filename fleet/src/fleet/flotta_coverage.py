"""flotta-menedzser: a menedzser-szerep box-oldali egészsége (a flotta_report kiegészítése).

    repair_probe() -> {"ok", "detail"}     a végrehajtó önpróbája (a jelentésbe kerül; ha piros vagy
                                           nem mért, a Worker a box menedzsereit alkalmatlannak veszi)
    lines(coverage) -> (problémák, figyelmeztetések)   a Worker válaszának `coverage`-e a doctor box-sorába
    unreachable(state, now) / clear()      a Worker elérhetetlensége: helyi tartalék-fájl + piros doctor

Piros: `ember-kell` incidens, és ha a Worker nem érhető el (a box így semmit nem jelent, és a
végrehajtó sem léphet). ⚠: fedetlen cél (v1-ben a box teljes kiesése mindig fedetlen, ezt a sor
kimondja), alkalmatlan menedzser, 2-nél több átadás.
"""
from __future__ import annotations
import json
import os
import tempfile
import time
from pathlib import Path

from fleet import CONFIG_DIR

UNREACHABLE = CONFIG_DIR / "state" / "flotta-unreachable.json"


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        fd, p = tempfile.mkstemp(dir=d, prefix=".probe-")
        os.close(fd)
        os.unlink(p)
        return True
    except OSError:
        return False


def repair_probe() -> dict:
    from fleet import maintenance, flotta_report, repair_lock
    from fleet.incident_cli import CLAIMS
    bad = [name for name, d in (("javító-zár", repair_lock.ROOT), ("karbantartási zár", maintenance._root()),
                                ("átvételek", CLAIMS)) if not _writable(Path(d))]
    if flotta_report.config() is None:
        bad.append("flotta.env")
    return {"ok": not bad, "detail": ("nem írható / hiányzik: " + ", ".join(bad)) if bad else "végrehajtó kész"}


def lines(cov) -> tuple[list[str], list[str]]:
    if not isinstance(cov, dict):
        return [], []
    probs, warn = [], []
    for x in cov.get("human_needed") or []:
        probs.append(f"ember kell: {x.get('target')} (incidens {x.get('incident')}) — a menedzserek nem javították")
    unc = [x for x in cov.get("uncovered") or [] if isinstance(x, dict)]
    if unc:
        warn.append("fedetlen: " + "; ".join(f"{x.get('target')} ({x.get('why', '')})" for x in unc[:10])
                    + " — kiesésnél azonnali e-mail megy")
    for x in cov.get("unfit") or []:
        warn.append(f"alkalmatlan menedzser: {x.get('agent')} — {x.get('why', '')}")
    for x in cov.get("handovers") or []:
        if int(x.get("handovers") or 0) > 2:
            warn.append(f"{x.get('handovers')} átadás: {x.get('target')} (incidens {x.get('incident')})")
    return probs, warn


def unreachable(st: dict, now: float | None = None) -> None:
    now = time.time() if now is None else now
    try:
        UNREACHABLE.parent.mkdir(parents=True, exist_ok=True)
        UNREACHABLE.write_text(json.dumps({"since_ok": st.get("last_ok"), "last_attempt": st.get("last_attempt"),
                                           "last_info": st.get("last_info"), "noted_at": now}))
    except OSError:
        pass


def clear() -> None:
    try:
        UNREACHABLE.unlink(missing_ok=True)
    except OSError:
        pass
