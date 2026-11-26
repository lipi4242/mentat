"""A prompt-drift restartok nyoma: napló, első üzenet, körönként egy összesítő.

Napló (`~/.config/fleet/state/prompt-drift.log`): soronként, tabulátorral
  időpont · ágens · ok · változott fájlok · eredmény
A journal (a reconcile kimenete) ugyanezt mondja; a fájl a hosszabb emlékezet.

Az első üzenet (`drift_notice` az ágens állapotában) a restart után a pane-be
megy, ugyanazokkal az őrökkel, mint a tick (tick_gate_inject.send). Ha a pane
még foglalt (indul, fut a startup), a következő kör újrapróbálja, NOTICE_TTL_S-ig.

Összesítő: a kör drift-eseményeiből EGY riasztás a meglévő alerts úton. A
kulcs az események azonosítóiból áll, így egy változatlanul várakozó vagy
keret nélküli ágens nem riaszt 5 percenként újra (alerts.REPEAT_S).
"""
from __future__ import annotations
import hashlib
import time

from fleet import CONFIG_DIR, alerts, prompt_drift, requested_stop
from fleet.prompt_drift_text import safe_name, shown

LOG_PATH = CONFIG_DIR / "state" / "prompt-drift.log"
NOTICE_TTL_S = 1800
_KINDS = {"resume_restart": "restart", "skip:drift-budget": "keret-elfogyott",
          "skip:drift-busy-long": "dolgozik-6h+", "skip:drift-untrusted": "csak-jelzes",
          "skip:drift-invalid-settings": "hibas-settings"}


def log_line(agent: str, why: str, files: list[str], result: str, now: float) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
    why = "".join(c if c.isprintable() and c != "\t" else " " for c in why)
    row = "\t".join([ts, safe_name(agent), why, ",".join(safe_name(f) for f in files) or "-", result])
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as f:
            f.write(row + "\n")
    except OSError:
        pass   # a journal-sor marad; a napló nem állíthatja meg a kört


def restart_logged(entry: dict, m: dict, result: str, now: float) -> None:
    files = shown(entry, m)
    log_line(entry["agent"], m.get("_reason") or prompt_drift.reason(entry, m), files, result, now)


def before_restart(entry: dict, m: dict, st: dict, now: float) -> None:
    """A restart ELŐTT: a kért jelölő elhasználva, az első üzenet sorban."""
    requested_stop.clear_restart(entry["agent"])
    st["drift_notice"] = {"text": prompt_drift.notice_text(entry, m), "until": now + NOTICE_TTL_S}


def event(entry: dict, action: str, reason: str, m: dict, st: dict, now: float) -> dict | None:
    """A kör egy összesítendő eseménye, vagy None (a rövid várakozás csak journal)."""
    kind = _KINDS.get(action)
    if kind is None:
        return None
    if kind == "restart":
        ident = f"{entry['agent']}:{int(now)}"
    elif kind == "keret-elfogyott":
        ident = f"{entry['agent']}:budget:{int(min(st.get('resume_restarts') or [now]))}"
    else:   # várakozás / nem megbízható / hibás: az epizód a drift kezdete
        ident = f"{entry['agent']}:{kind}:{int(st.get('prompt_drift_since') or 0)}"
    files = shown(entry, m)
    return {"agent": entry["agent"], "kind": kind, "reason": reason, "files": files,
            "result": m.get("_drift_result") or kind, "id": ident}


def summarize(events: list[dict], host: str | None, now: float, env_for) -> str | None:
    """EGY riasztás a kör eseményeiből; a sorok a naplóba is (ha nem ismétlés)."""
    if not events:
        return None
    key = "prompt-drift:" + hashlib.sha256("|".join(sorted(e["id"] for e in events)).encode()).hexdigest()[:16]
    lines = [f"🔄 {host or '?'}: prompt-változás / kért újraindítás ({len(events)} ágens)"]
    for e in events:
        lines.append(f"- {e['agent']}: {e['result']} — {e['reason']}")
    res = alerts.alert(key, "\n".join(lines), agent_env_file=env_for(events[0]["agent"]), now=now)
    if res != "dup":
        for e in events:
            if e["kind"] != "restart":   # a restart sorát a végrehajtás már írta
                log_line(e["agent"], e["reason"], e["files"], e["result"], now)
    return res


def deliver_notice(entry: dict, st: dict, now: float, *, save, log, send=None) -> None:
    """A függő első üzenet beküldése; siker vagy lejárat után törlődik."""
    n = st.get("drift_notice")
    if not isinstance(n, dict):
        return
    a = entry["agent"]
    if now > float(n.get("until") or 0):
        st["drift_notice"] = None
        save(a, st)
        log(f"{a}: az újraindítás-üzenet {NOTICE_TTL_S // 60} percig nem ment be — elengedem")
        return
    if send is None:
        from fleet.tick_gate_inject import send
    ok, why = send(entry["session"], n.get("text") or "")
    if ok:
        st["drift_notice"] = None
        save(a, st)
        log(f"{a}: újraindítás-üzenet beküldve")
    else:
        log(f"{a}: újraindítás-üzenet még nem ment be ({why}) — a következő kör újrapróbálja")
