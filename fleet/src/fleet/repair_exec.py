"""flotta-menedzser: `fleet repair-exec <incidens> <lépés> [--agent A] [--cause C]` — a javító végrehajtó.

Minden javító lépés ezen megy, a célboxon; szabad parancs nincs (repair_steps.STEPS). Sorrend, kódban:
  1. helyi kizárólagos zár a célra (repair_lock; a box-szintű lépés minden ágens-zárral ütközik);
  2. a zár birtokában a Worker ellenőrzi az átvételt (fence + titok + op_id + lépés + cél) —
     nem érvényes vagy nem elérhető: NEM lép;
  3. újraindító lépésnél: a karbantartási zár (`fleet lock`, a reconcile és a tick tiszteli); dolgozó
     ágensnél (friss transzkript) várakozás a kísérleti keret végéig, utána „busy”;
  4. a szándék rögzítése a Workerben (újraindítási keret foglalása op_id-vel);
  5. végrehajtás (kivétel → „uncertain”; a registry lenyomata előtte/utána — változás → „uncertain”);
  6. az eredmény rögzítése (elavult fence-szel a Worker nem fogadja el).
`postcheck`: a Worker nonce-ot ad, friss képesség-próba a nonce-szal és a processz boot-azonosítójával;
csak a zöld, nonce-os eredmény zár. Elérés (v1): csak a SAJÁT box registry-ágensei.

Kilépés: 0 rendben · 1 a lépés nem sikerült / bizonytalan / dolgozó ágens / piros ellenőrzés ·
2 használati hiba (lépés, ágens, nincs átvétel) · 3 a cél zárja foglalt · 4 a Worker elutasította
vagy nem elérhető (semmi nem történt, vagy az eredmény elavult) · 5 ember kell (keret elfogyott,
nem dönthető el, nem igazolható ok).
"""
from __future__ import annotations
import sys
import time
import uuid
from datetime import datetime

from fleet import maintenance, repair_lock, repair_steps
from fleet.incident_cli import claim_path, load_claim

OK, FAIL, USAGE, LOCKED, WORKER, HUMAN = 0, 1, 2, 3, 4, 5
POLL_S = 30


def _until(iso: str | None) -> float:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _crashed_executor_lock(agent: str, marker) -> bool:
    """Egy összeomlott végrehajtó zárja-e: a jelölő a zárjelét tartja, és a zárfájlban még pontosan az áll.
    Ha egy ember az összeomlás után saját zárat vett (`fleet lock`), a tartalom eltér: nem vesszük át."""
    try:
        token = marker.read_text().strip()
    except OSError:
        return False
    return bool(token) and maintenance.content(agent) == token


def _target(step, agent, host, agents) -> tuple[str | None, dict | None, str]:
    if step == "doctor" and agent is None:
        return (f"box:{host}", None, "") if host else (None, None, "ez a gép nincs a registryben")
    if agent is None:
        return None, None, f"a(z) {step} lépéshez --agent kell"
    e = next((x for x in agents if x["agent"] == agent), None)
    if e is None:
        return None, None, f"{agent} nincs ezen a boxon ({host}) — v1-ben csak a saját box érhető el"
    return f"agent:{agent}", e, ""


def _execute(step, entry, cause, steps):
    if step == "doctor":
        return steps.doctor(entry)
    if step == "doctor-fix":
        return steps.doctor_fix(entry)
    if step == "bridge-install":
        return steps.bridge_install(entry)
    if step == "unquarantine":
        return steps.unquarantine(entry, cause)
    raise ValueError(f"nem engedélyezett lépés: {step}")   # a STEPS-szűrő után ide nem jut


def _verify(incident, entry, worker, steps, say) -> int:
    ok, v = worker.verify_start()
    if not ok:
        say(f"ellenőrzés: a Worker nem ad nonce-ot ({v.get('code')})")
        return WORKER
    try:
        green, boot, summary = steps.probe(entry)
    except Exception as e:  # noqa: BLE001 — a próba hibája piros, nem zöld
        green, boot, summary = False, "-", f"a próba kivétellel állt meg: {type(e).__name__}"
    if green:   # a zöldet egy friss box-jelentés bizonyítja a Workernek (nem a mi szavunk): előbb jelentünk
        try:
            if not steps.report_now(entry):
                say("ellenőrzés: a friss box-jelentés nem ment ki — a Worker nem zárhat; később futtasd újra")
        except Exception as e:  # noqa: BLE001
            say(f"ellenőrzés: a friss box-jelentés hibája ({type(e).__name__})")
    ok, r = worker.verify_result(v.get("nonce", ""), boot, bool(green), repair_steps.scrub(summary))
    if not ok:
        say(f"ellenőrzés: az eredményt a Worker nem fogadta el ({r.get('code')})")
        return WORKER
    say(f"ellenőrzés: {'ZÖLD' if green else 'piros'} → {r.get('state')} · {summary[:300]}")
    if r.get("state") == "megoldva":
        claim_path(incident).unlink(missing_ok=True)
        return OK
    return FAIL


def _step(incident, step, target, entry, cause, worker, steps, op_id, until, now, sleep, say) -> int:
    agent = entry["agent"] if entry else None
    if agent and step in repair_steps.RESTART_STEPS:
        while steps.busy(entry):
            if now() >= until:
                worker.result(op_id, "busy", "az ágens a kísérleti keret végéig dolgozott — nem indítottam újra",
                              step=step, target=target)
                say(f"{agent} dolgozik (friss transzkript), a keret lejárt — nem indítom újra")
                return FAIL
            sleep(POLL_S)
    ok, res = worker.intent(op_id, step, target)
    if not ok:
        say(f"a Worker nem rögzítette a szándékot ({res.get('code')})")
        return HUMAN if res.get("code") == "budget" else WORKER
    before = steps.registry_digest()
    if before is None:   # nem mérhető: a tripwire most vak — ezt kimondjuk, nem csendben átengedjük
        say("FIGYELEM: a registry lenyomata nem mérhető — a registry-tripwire ennél a lépésnél nem véd")
    try:
        outcome, summary, assessment = _execute(step, entry, cause, steps)
    except Exception as e:  # noqa: BLE001 — összeomlott lépés: a hatása nem ismert
        outcome, summary, assessment = "uncertain", f"a lépés kivétellel állt meg: {type(e).__name__}", None
    try:
        after = steps.registry_digest()
    except Exception:  # noqa: BLE001 — nem mérhető utólag: a hatás nem ismert, de az eredmény akkor is megy
        after = object()
    if before is None:
        summary = f"{summary}; registry-tripwire: nem mérhető"
    elif after != before:
        outcome, summary = "uncertain", f"{summary}; a REGISTRY megváltozott a lépés alatt, vagy nem mérhető (tilos / bizonytalan)"
    ok, res = worker.result(op_id, outcome, repair_steps.scrub(summary), assessment)
    say(f"{step} {target}: {outcome}{' / ' + assessment if assessment else ''} · {summary[:300]}")
    if not ok:
        say(f"az eredményt a Worker nem fogadta el ({res.get('code')}) — elavult átvétel?")
        return WORKER
    if outcome == "refused" or assessment == "undecidable":
        return HUMAN
    return OK if outcome == "ok" else FAIL


def run(incident: str, step: str, agent: str | None = None, cause: str | None = None, *, worker=None,
        steps=repair_steps, host: str | None = None, agents: list[dict] | None = None,
        now=time.time, sleep=time.sleep, say=print) -> int:
    if step not in repair_steps.STEPS:
        say(f"nem engedélyezett lépés: {step!r} (csak: {', '.join(repair_steps.STEPS)})")
        return USAGE
    if agents is None or host is None:
        from fleet.registry import agents_for_host, local_host
        host = host or local_host()
        agents = agents if agents is not None else agents_for_host(host or "")
    target, entry, why = _target(step, agent, host, agents)
    claim = load_claim(incident) if target else None
    if target is None or claim is None:
        say(why or f"nincs átvétel ezen a boxon: {incident} (előbb `fleet incident claim`)")
        return USAGE
    if claim.get("target") and claim["target"] != target:
        say(f"az átvétel célja {claim['target']}, nem {target}")
        return USAGE
    if agent and claim.get("as") == agent:   # engedély-mátrix: a saját unitját sosem ő indítja újra
        say(f"{agent} a saját incidensét nem javítja — egy másik menedzser dolga")
        return USAGE
    from fleet import kepesseg
    if entry and kepesseg.is_desktop(entry) and step in repair_steps.RESTART_STEPS:
        say(f"{agent} saját gépen fut (nincs always-on processz/unit/híd): a(z) {step} itt nem értelmezhető — "
            "csak doctor és postcheck; a javítás a tulajdonos sessionjében történik")
        return USAGE
    if worker is None:
        from fleet.repair_client import Worker
        worker = Worker(incident, claim)
    try:
        with repair_lock.held(agent):
            op_id = uuid.uuid4().hex
            ok, res = worker.check(op_id, step, target)
            if not ok:
                say(f"a Worker nem engedi ({res.get('code')}) — nem lépek")
                return WORKER
            if res.get("must_assess") and step != "doctor":
                say("egy korábbi lépés kimenete bizonytalan: előbb `doctor` (csak olvas) kell")
                return WORKER
            if step == "postcheck":
                return _verify(incident, entry, worker, steps, say)
            restart = agent is not None and step in repair_steps.RESTART_STEPS
            marker = repair_lock.ROOT / f"maint-{agent}"
            if restart and maintenance.is_locked(agent) and not _crashed_executor_lock(agent, marker):
                say(f"{agent}: kézi karbantartási zár alatt áll — nem nyúlok hozzá")
                return WORKER
            until = _until(res.get("attempt_until"))
            try:
                if restart:   # a zár és a jelölő a try-ban: ha a jelölő írása bukik, a zár is felszabadul
                    maintenance.lock(agent, max(5, int((until - now()) / 60) + 15), own=True)
                    marker.write_text(maintenance.content(agent) or "")   # a jelölő a MI zárunk jele
                return _step(incident, step, target, entry, cause, worker, steps, op_id, until, now, sleep, say)
            finally:
                if restart:
                    try:
                        maintenance.release_own(agent)   # csak a saját zárunkat: egy közben vett kézi zár marad
                    finally:
                        marker.unlink(missing_ok=True)
    except repair_lock.Busy as e:
        say(str(e))
        return LOCKED


def cmd_repair_exec(a) -> int:
    return run(a.incident, a.step, a.agent, a.cause)


def add_parser(sub) -> None:
    x = sub.add_parser("repair-exec", help="a javító végrehajtó (flotta-menedzser): egy engedélyezett lépés egy átvett incidensen; "
                       "kilépés 0 rendben · 1 nem sikerült · 2 használat · 3 zár foglalt · 4 Worker elutasította · 5 ember kell")
    x.add_argument("incident")
    x.add_argument("step", choices=repair_steps.STEPS)
    x.add_argument("--agent", help="a cél ágens (a box-szintű `doctor`-nál elhagyható)")
    x.add_argument("--cause", help=f"csak az unquarantine-nál: {' | '.join(repair_steps.CAUSES)}")
    x.set_defaults(fn=cmd_repair_exec)
