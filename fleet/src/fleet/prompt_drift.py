"""Prompt-drift: a futó processz óta tartalmilag változott a betöltött prompt.

A processz egy generációja (pid + indulási idő) az első reconcile-körben kap
alapvonalat (prompt_files.snapshot). Tartalék erre az egy körre: ami az
indulás UTÁN módosult (mtime), azt a processz nem láthatta — STALE jelet kap,
és driftként él a restartig. A további körök hashelnek és összevetnek.

Döntés (tiszta, `acts`), sorrendben:
  * nem megbízható változás (prompt_trust: git-en kívül, HEAD-től eltér,
    hooks-változás) vagy hibás settings → nincs restart, csak jelzés
  * dolgozó ágens → vár; WAIT_ALERT_S után jelez, de nem kényszerít
  * a változott fájlok még nem STABLE_S óta stabilak → vár (egy kiadási
    hullám = egy restart)
  * a resume-keret (RESUME_BUDGET / RESUME_WINDOW_S, NEM a crash-keret) elfogyott → jelzés
  * különben `resume_restart` (a unit `--resume`-mal indul, postcheck, első üzenet)
Az ágens saját kérése (`fleet request-restart`) ugyanezen az úton megy,
rövidebb tétlenségi küszöbbel (REQUEST_IDLE_S).
"""
from __future__ import annotations
import hashlib
from pathlib import Path

from fleet import prompt_files, prompt_trust
from fleet.liveness import TRANSCRIPT_FRESH_S
from fleet.prompt_drift_text import notice_text, reason  # noqa: F401  (a hívók innen érik el)

RESUME_BUDGET = 3              # drift- és kért restart / ágens / ablak
RESUME_WINDOW_S = 6 * 3600
WAIT_ALERT_S = 6 * 3600        # ennyi várakozás után jelez a dolgozó ágensről
REQUEST_IDLE_S = 60            # a kért restart ennyi tétlenség után jöhet
STABLE_S = 15 * 60             # ennyi ideig változatlan drift után indul a restart
STALE = "mtime-az-indulas-utan"
_BLOCKING = ("start", "restart", "planned_restart", "stop", "recheck", "rearm")


def generation(m: dict) -> list | None:
    d = ((m.get("signals") or {}).get("process") or {}).get("data") or {}
    return None if d.get("pid") is None else [d.get("pid"), d.get("started_s")]


def _baseline(entry: dict, m: dict, st: dict, gen: list, cur: dict, now: float, home, newer) -> None:
    late = newer([k for k, h in cur.items() if h], gen[1]) if gen[1] is not None else []
    settings = prompt_files.settings_paths(entry, home or Path.home())
    hooks = {str(p): (prompt_trust.UNKNOWN_HOOKS if str(p) in late else prompt_trust.hooks_fp(p)) for p in settings}
    st["prompt_baseline"] = {"gen": gen, "taken_at": now, "hashes": dict(cur, **{k: STALE for k in late}),
                             "hooks": hooks}
    m["prompt_drift"] = late
    _mark(st, late, cur, now)


def _mark(st: dict, diff: list, cur: dict, now: float) -> None:
    """A drift kezdete és a stabilitás órája: új tartalom → az óra újraindul."""
    sig = hashlib.sha256(repr([(k, cur.get(k)) for k in diff]).encode()).hexdigest()[:16] if diff else None
    if not diff:
        st["prompt_drift_since"] = st["prompt_drift_stable_since"] = st["prompt_drift_sig"] = None
        return
    st["prompt_drift_since"] = st.get("prompt_drift_since") or now
    if st.get("prompt_drift_sig") != sig:
        st["prompt_drift_sig"], st["prompt_drift_stable_since"] = sig, now


def observe(entry: dict, m: dict, st: dict, now: float, *, snap=prompt_files.snapshot,
            home: Path | None = None, newer=prompt_files.newer_than, git_run=None) -> bool:
    """A kör eleje: alapvonal vagy összevetés. `m["prompt_drift"]` = változott utak,
    `m["prompt_drift_block"]` = (None|invalid|untrusted, indok). Visszaad: írni kell-e."""
    m["prompt_drift"], m["prompt_drift_block"] = [], (None, "")
    gen = generation(m)
    if gen is None or m["signals"]["process"]["state"] != "up":
        return False
    cur = snap(entry, home)
    if cur is None:
        return False                     # időkeret elfogyott: ebben a körben nincs mérés
    before = dict(st)
    base = st.get("prompt_baseline") or {}
    if base.get("gen") != gen:
        _baseline(entry, m, st, gen, cur, now, home, newer)
    else:
        m["prompt_drift"] = prompt_files.changed(base.get("hashes") or {}, cur)
        _mark(st, m["prompt_drift"], cur, now)
    if m["prompt_drift"]:
        kw = {"run": git_run} if git_run else {}
        m["prompt_drift_block"] = prompt_trust.check(
            entry.get("workdir") or ".", m["prompt_drift"], (st["prompt_baseline"].get("hooks") or {}),
            prompt_files.settings_paths(entry, home or Path.home()), **kw)
    return st != before


def resume_left(st: dict, now: float) -> int:
    recent = [t for t in st.get("resume_restarts", []) if now - t < RESUME_WINDOW_S]
    return max(0, RESUME_BUDGET - len(recent))


def acts(entry: dict, m: dict, st: dict, now: float, prior: list) -> list[tuple[str, str]]:
    """Pure: a drift/kérés döntése; üres, ha nincs mit tenni vagy más beavatkozás már fut."""
    drift, req = m.get("prompt_drift") or [], bool(m.get("restart_requested"))
    if not drift and not req:
        return []
    if any(a in _BLOCKING for a, _ in prior):
        return []                       # egy másik restart úgyis friss promptot tölt be
    why = reason(entry, m)
    kind = (m.get("prompt_drift_block") or (None, ""))[0] if drift else None
    if kind == prompt_trust.INVALID:
        return [("skip:drift-invalid-settings", f"nincs restart — {why}")]
    if kind == prompt_trust.UNTRUSTED:
        return [("skip:drift-untrusted", f"nincs automatikus restart — {why}")]
    age = m.get("transcript_age_s")
    if age is None or age <= (REQUEST_IDLE_S if req and not drift else TRANSCRIPT_FRESH_S):
        since = st.get("prompt_drift_since") or now
        if drift and now - since > WAIT_ALERT_S:
            return [("skip:drift-busy-long", f"{int((now - since) // 3600)} órája dolgozik, a restart vár — {why}")]
        return [("skip:drift-busy", f"dolgozik, a restart vár — {why}")]
    stable = now - (st.get("prompt_drift_stable_since") or now)
    if drift and stable < STABLE_S:
        return [("skip:drift-settling", f"a változás {int(stable // 60)} perce stabil (kell {STABLE_S // 60}) — {why}")]
    if resume_left(st, now) == 0:
        return [("skip:drift-budget", f"a resume-keret ({RESUME_BUDGET}/{RESUME_WINDOW_S // 3600} óra) "
                                      f"elfogyott, nem indítom újra — {why}")]
    return [("resume_restart", why)]
