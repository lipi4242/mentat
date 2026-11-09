"""Restart utáni ellenőrzés. Egy restart nem "kész", amíg ez nem zöld.

Amit 2026-09-16 este két külön hibából tanultunk: egy újraindítás (1) leszakadt
RC-vel jöhet vissza, (2) elindíthat egy telegram-plugin pollert, ami a saját
hídja elől lopja a tokent (409). Mindkettő NÉMA — a unit `active`, a tmux
session él, a heartbeat friss. Ezért a restart mellékhatásait külön kell
megnézni, a restart után, nem előtte.

Háromértékű (Codex F1-review): `ok` · `pending` · `failed`. `ok` = minden
KÖTELEZŐ jel bizonyítottan jó: processz (új generáció), csatorna,
ütemezés (egy tick landolt a restart UTÁN), auth. A `pending` várakozás a
türelmi időn belül; a türelmi idő lejárta után ami még mindig nem dőlt el, az
`failed` — nem esik ki csendben. Türelmi idő: PENDING_MAX_S, az ütemezésnél
az ágens saját periódusa + indulási fej (arming.deadline_s), mert egy 17 órás
ágens első tickje nem várható 15 percen belül.

Az RC nem kötelező: a transzkript a visszakapcsolódást nem naplózza
(signals.rc_verdict), ezért az `unknown` RC-re bukni karantént jelentene egy
mérési korlát miatt. Az `unknown` RC-t viszont kiírjuk, nem nyeljük le.

2026-10-14-ig a `pending` ütemezés és az `unknown` auth OK-t adott: egy ágens
startup-parancsa 30 napig nem ment be, és a postcheck zöld volt.

Képesség (11-07, kepesseg.py): a jelek infrastruktúrát mérnek. 11-07-én minden jel zöld volt,
és három ágens nem tudott írni a tulajdonosnak. Ezért a postcheck a küldést (dry-run), a todót,
a saját állapotot és a gitet le is futtatja; ami piros, az `failed`. A `capability_only` jelzi,
ha csak ez bukott: restart ezen nem segít, a reconcile ilyenkor nem karanténoz, hanem
független úton riaszt (alerts.py).
"""
from __future__ import annotations
import time

from fleet import signals
from fleet.arming import deadline_s
from fleet.liveness import DEFAULT_TICK_PERIOD_S

OK, PENDING, FAILED = "ok", "pending", "failed"
PENDING_MAX_S = 15 * 60


def window_s(entry: dict) -> float:
    """Meddig lehet egy restart utáni postcheck `pending` (ágensenként)."""
    if not entry.get("proactive"):
        return PENDING_MAX_S
    period = float(entry.get("tick_period_s") or DEFAULT_TICK_PERIOD_S)
    return max(PENDING_MAX_S, deadline_s(period))


def _schedule(s: dict, restart_at: float | None, now: float) -> tuple[bool, str]:
    """(bizonyított-e, indok). Restart után csak a restart UTÁNI tick számít:
    a korábbi `last-tick.json` az előző generáció bizonyítéka (arming.py)."""
    sch = s["schedule"]
    st = sch["state"]
    # A flotta timerének tickje nem a claude-processzen múlik: egy restart nem
    # bizonyítja és nem rontja el. Az elakadását a reconcile csend-riasztása
    # jelzi; itt bukni karantént jelentene egy nem-claude hiba miatt.
    if st == "n/a" or (sch.get("data") or {}).get("owner") == "fleet":
        return True, ""
    age = (sch.get("data") or {}).get("tick_age_s")
    if st == "armed" and (restart_at is None or (age is not None and age < now - restart_at)):
        return True, ""
    if st == "armed":
        return False, "ütemezés: a restart óta még nem landolt tick (a látott tick az előző generációé)"
    return False, f"ütemezés {st}: {sch['detail']}"


def postcheck_verdict(m: dict, *, restart_at: float | None, now: float,
                      grace_over: bool, schedule_over: bool | None = None) -> tuple[str, list[str]]:
    """Pure: (státusz, problémák vagy várakozások). `schedule_over` híján az
    ütemezés türelmi ideje is `grace_over`."""
    schedule_over = grace_over if schedule_over is None else schedule_over
    s = m["signals"]
    problems: list[str] = []
    pending: list[str] = []

    def wait(msg: str, over: bool) -> None:
        (problems if over else pending).append(msg + (" — a türelmi idő lejárt" if over else ""))

    proc = s["process"]
    if proc["state"] == "down":
        problems.append("a claude-processz nem fut a várt --remote-control névvel")
    elif proc["state"] != "up":
        problems.append(f"a processz nem mérhető ({proc['state']}): {proc['detail']}")
    elif restart_at is not None:
        started = proc["data"].get("started_s")
        if started is None:
            wait("a processz indulási ideje nem olvasható", grace_over)
        elif started < restart_at - 5:
            problems.append("a futó processz RÉGEBBI, mint a restart — a restart nem történt meg")
    if m["pollers"]:
        problems.append(f"telegram-plugin poller fut az ágens alatt: pid {m['pollers']}")
    ch = s["channel"]
    if ch["state"] == "conflict":
        problems.append(ch["detail"])
    elif ch["state"] not in ("ok", "n/a"):
        wait(f"csatorna {ch['state']}: {ch['detail']}", grace_over)
    if s["rc"]["state"] == "disconnected":
        problems.append("RC leszakadt a restart óta")
    proven, why = _schedule(s, restart_at, now)
    if not proven:
        wait(why, schedule_over)
    auth = s.get("auth") or {"state": signals.UNKNOWN, "detail": "az auth-jel hiányzik a mérésből"}
    if auth["state"] == "expired":
        problems.append(f"auth: {auth['detail']}")
    elif auth["state"] != "ok":
        wait(f"auth {auth['state']}: {auth['detail']}", grace_over)
    if problems:
        return FAILED, problems
    if pending:
        return PENDING, pending
    return OK, []


def _capability(entry: dict) -> dict:
    from pathlib import Path
    from fleet import kepesseg
    return kepesseg.check(entry, Path.home())


def postcheck(entry: dict, *, restart_at: float | None = None, wait_s: int = 90,
              poll_s: int = 10, sleep=time.sleep, measure=signals.measure,
              now=time.time, capability=_capability) -> dict:
    """Legfeljebb `wait_s`-ig vár, hogy egy ÚJ processz feljöjjön, aztán ítél."""
    waited = 0
    m = measure(entry)

    def fresh(mm):
        p = mm["signals"]["process"]
        if p["state"] != "up":
            return False
        if restart_at is None:
            return True
        st = p["data"].get("started_s")
        return st is None or st >= restart_at - 5

    while not fresh(m) and waited < wait_s:
        sleep(poll_s)
        waited += poll_s
        m = measure(entry)
    t = now()
    since = None if restart_at is None else t - restart_at
    status, notes = postcheck_verdict(m, restart_at=restart_at, now=t,
                                      grace_over=since is not None and since > PENDING_MAX_S,
                                      schedule_over=since is not None and since > window_s(entry))
    rc = m["signals"]["rc"]
    cap = capability(entry) if status != FAILED else {"red": [], "unknown": [], "ok": []}
    only = status != FAILED and bool(cap["red"])
    if only:
        status, notes = FAILED, [f"képesség: {x}" for x in cap["red"]]
    return {"agent": entry["agent"], "status": status, "ok": status == OK,
            "problems": notes if status == FAILED else [],
            "pending": notes if status == PENDING else [],
            "unknown": ([f"rc (nem kötelező): {rc['detail']}"] if rc["state"] == signals.UNKNOWN else [])
            + cap["unknown"], "capability_only": only, "capability_ok": cap["ok"],
            "waited_s": waited, "measure": m}


def format_postcheck(r: dict) -> str:
    head = f"postcheck {r['agent']}: {r['status'].upper()} ({r['waited_s']} s várva)"
    body = "".join(f"\n  - {p}" for p in r["problems"] + r["pending"])
    body += "".join(f"\n  ? nem mérhető: {p}" for p in r.get("unknown", []))
    if r.get("capability_ok"):
        body += "\n  képesség: " + " · ".join(r["capability_ok"]) + " ✓"
    sig = r["measure"]["signals"]
    tail = "\n  " + " · ".join(f"{k}={v['state']}" for k, v in sig.items())
    return head + body + tail
