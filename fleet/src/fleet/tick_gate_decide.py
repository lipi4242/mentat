"""A kapu döntése egy ellenőrzés után — TISZTA.

`decide(cfg, gate, obs, now=, last_tick_at=, busy=)` → {"action", "why", "next_due_at",
"interval_s", "state"}; az `action`:

    inject   be kell küldeni a tick-parancsot (a futtató küldi; bukásnál `deferred(...)`)
    idle     nincs beküldenivaló — a commit lép (látott PR-ok, todo-kurzor)
    busy     lenne munka, de az ágens dolgozik / ablaknál áll / lease él: a commit NEM lép
    capped   lenne munka, de a hurok-korlát (min. távolság, napi plafon) tiltja
    error    a megfigyelés hibás, és az utolsó tick még friss (< idle_s): kimarad

Hálózati hibánál a beküldés csak akkor jár, ha az utolsó tick régebbi, mint `idle_s`.
"""
from __future__ import annotations

import time

from fleet import tick_gate as tg

ERRORS_RED = 3   # ennyi egymást követő hibás ellenőrzés után piros a nyom


def _day(now: float, tz: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(now, ZoneInfo(tz)).strftime("%Y-%m-%d")


def decide(cfg: dict, gate: dict, obs: dict, *, now: float, last_tick_at: float | None,
           busy: str | None) -> dict:
    st = dict(gate)
    st["checked_at"] = now
    st["errors"] = int(st.get("errors") or 0) + 1 if obs.get("error") else 0
    st["error"] = obs.get("error")
    if obs.get("activity"):   # csak a VALÓDI munka-jel: a napi kör és a hiba-tartalék nem tartja sűrűn
        st["last_activity_at"] = now
    want = bool(obs.get("reasons"))
    why = list(obs.get("reasons") or [])
    if obs.get("error") and not want:
        # visszalépő küszöb (Codex): tartós GitHub-kiesésnél 1, 2, 4, 8 óránként egy tick, nem óránként
        limit = (cfg.get("idle_s") or tg.base_period_s(cfg)) * 2 ** (min(st["errors"], 4) - 1)
        if last_tick_at is None or now - last_tick_at > limit:
            want, why = True, [f"az ellenőrzés hibás, és az utolsó tick régebbi, mint {limit // 60} perc"]
    interval = tg.interval_s(cfg, st.get("last_activity_at"), now)
    res = {"interval_s": interval, "why": why, "state": st}
    if not want:
        st.update(obs.get("commit") or {})
        st.pop("pending_since", None)
        res["action"] = "error" if obs.get("error") else "idle"
        return _next(res, cfg, now, interval)
    day = _day(now, cfg["tz"])
    count = int(st.get("day_count") or 0) if st.get("day") == day else 0
    gap = min(cfg.get("active_s") or tg.base_period_s(cfg), tg.base_period_s(cfg)) - tg.SLACK_S
    st.setdefault("pending_since", now)   # a munka mióta vár beküldésre (inject törli)
    if count >= int(cfg["max_per_day"]) or (st.get("injected_at") and now - st["injected_at"] < gap):
        res["action"] = "capped"
        res["why"] = why + [f"hurok-korlát: {count}/{cfg['max_per_day']} ma, utolsó beküldés "
                            f"{int(now - (st.get('injected_at') or now)) // 60} perce"]
        return _next(res, cfg, now, tg.base_period_s(cfg) if cfg.get("at") else int(cfg.get("active_s")))
    if busy or obs.get("busy"):
        res["action"] = "busy"
        res["why"] = why + [busy or obs["busy"]]
        # a következő tüzelésnél újra (a munka nem vész el: a commit nem lépett)
        return _next(res, cfg, now, tg.base_period_s(cfg) if cfg.get("at") else int(cfg.get("active_s")))
    res["action"] = "inject"
    commit = obs.get("commit") or {}
    # nyugtára vár: ha az ágens a beküldés után nem mozdul, a következő futás visszaállítja ezt
    st["await_ack"] = {"at": now, "prev": {k: gate.get(k) for k in commit}}
    st.update(commit)
    st.pop("pending_since", None)
    st.update(injected_at=now, day=day, day_count=count + 1)
    return _next(res, cfg, now, tg.interval_s(cfg, st.get("last_activity_at"), now))


ACK_GRACE_S = 15    # a beküldés előtti ennyi mp is elfogadott (óra-pontatlanság; a foglaltság-őr
                    # miatt a beküldéskor a transzkript legalább TRANSCRIPT_FRESH_S-e nem íródott)
ACK_WAIT_S = 300    # ennyi idő kell a beküldés után, mielőtt „nem érkezett meg”-et mondunk (Codex)


def settle_ack(gate: dict, transcript_mtime: float | None, now: float | None = None) -> tuple[dict, str | None]:
    """Pure. Az előző beküldés megérkezett-e (a transzkript a beküldés után íródott)? Ha nem: a
    commit visszaáll (a munka újra látszik), és az ok bekerül a nyomba. Ismeretlen transzkript:
    elfogadjuk (asztali/mérhetetlen eset; a nyom mutatja)."""
    ack = gate.get("await_ack")
    if not isinstance(ack, dict) or not isinstance(ack.get("at"), (int, float)):
        return gate, None
    now = time.time() if now is None else now
    if transcript_mtime is None and now - ack["at"] < ACK_WAIT_S:
        return gate, None
    if transcript_mtime is not None and transcript_mtime < ack["at"] - ACK_GRACE_S and now - ack["at"] < ACK_WAIT_S:
        return gate, None   # még korai ítélni: a következő futás dönt
    st = dict(gate)
    st.pop("await_ack", None)
    if transcript_mtime is None or transcript_mtime >= float(ack["at"]) - ACK_GRACE_S:
        return st, None
    for k, v in (ack.get("prev") or {}).items():
        if v is None:
            st.pop(k, None)
        else:
            st[k] = v
    # az injected_at MARAD (a min. távolság-őr és a hiba-tartalék története), a napi keret visszajár
    if st.get("day_count"):
        st["day_count"] = int(st["day_count"]) - 1
    return st, "az előző beküldés nem érkezett meg (a transzkript nem mozdult) — újra"


def deferred(res: dict, gate: dict, cfg: dict, why: str, now: float | None = None) -> dict:
    """A beküldés bukott (ablak, tmux-hiba): a commit visszavonva, mintha foglalt lett volna."""
    now = time.time() if now is None else now
    st = dict(gate)
    st.update(checked_at=res["state"]["checked_at"], errors=res["state"]["errors"],
              error=res["state"]["error"], last_activity_at=res["state"].get("last_activity_at"))
    st.setdefault("pending_since", now)
    out = {**res, "action": "busy", "why": res["why"] + [why], "state": st}
    return _next(out, cfg, now, tg.base_period_s(cfg) if cfg.get("at") else int(cfg.get("active_s")))


def _next(res: dict, cfg: dict, now: float, interval: int) -> dict:
    res["interval_s"] = interval
    res["next_due_at"] = now + interval
    res["state"].update(next_due_at=res["next_due_at"], interval_s=interval, decision=res["action"],
                        reasons=res["why"][:20])
    return res
