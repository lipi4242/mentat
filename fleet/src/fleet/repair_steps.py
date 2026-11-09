"""flotta-menedzser: a javító végrehajtó engedélylistája — a lépések maguk, rögzített függvényekként.

Lépés (a Workerrel azonos szó)   mit csinál                                        újraindít?
  doctor                          `fleet doctor <ágens>` csak olvas; ágens nélkül a box-sor
  doctor-fix                      `fleet doctor <ágens> --fix` (reconcile egy ágensre)   igen
  bridge-install                  `fleet bridge install <ágens>`                          igen
  unquarantine                    karantén feloldása, CSAK gépileg igazolt okkal          igen
  postcheck                       ellenőrző próba a nonce-hoz (repair_exec.verify)

Minden lépés eredménye (kimenet, összefoglaló, felmérés): kimenet `ok|failed|refused`, a felmérés
csak a doctornál: `decided` (egészséges, vagy ismert hibákkal piros) / `undecidable` (ismeretlen,
függő). Szabad parancs, szabad argumentum nincs; az összefoglalóból a tokennek látszó szöveg kikerül.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

STEPS = ("doctor", "doctor-fix", "bridge-install", "unquarantine", "postcheck")
RESTART_STEPS = frozenset({"doctor-fix", "bridge-install", "unquarantine"})
#: Gépileg igazolható karantén-okok (a többi: refused → a Worker ember-kell-be teszi).
CAUSES = ("login-renewed", "bridge-conflict-gone")
MAX_SUMMARY = 1000

_SECRET = re.compile(r"mentat_[A-Za-z0-9_-]{8,}|\b\d{6,12}:[A-Za-z0-9_-]{30,}\b|\b(?:sk|re|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{10,}"
                     r"|\b[A-Za-z0-9+/_-]{40,}={0,2}")


def scrub(text: str) -> str:
    return _SECRET.sub("[kitakarva]", str(text))[:MAX_SUMMARY]


def registry_digest() -> str | None:
    """A registry könyvtár lenyomata (tripwire): a lépés nem írhat bele."""
    try:
        from fleet import registry_dir
        root = registry_dir()
        h = hashlib.sha256()
        for p in sorted(x for x in root.rglob("*") if x.is_file()):
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0")
        return h.hexdigest()
    except Exception:  # noqa: BLE001 — nem mérhető: a két oldalon ugyanúgy None
        return None


def busy(entry: dict) -> bool:
    """Dolgozik-e most (friss transzkript, mint a box-upgrade-nél). Néma, de élő ágens: nem."""
    from fleet import signals
    from fleet.box_ctx import BUSY_S
    age = signals.measure(entry).get("transcript_age_s")
    return age is not None and age < BUSY_S


def _lines(r: dict) -> str:
    return "; ".join((r.get("problems") or []) + [f"? {x}" for x in r.get("unknown") or []]
                     + [f"… {x}" for x in r.get("pending") or []])


def _desktop_check(entry: dict) -> dict:
    from fleet import kepesseg
    return kepesseg.check(entry, Path.home(), desktop=True)


def doctor(entry: dict | None) -> tuple[str, str, str]:
    from fleet import doctor as d, kepesseg
    if entry and kepesseg.is_desktop(entry):   # paritás: saját gépen nincs unit/processz-jel, a képesség mérhető
        cap = _desktop_check(entry)
        known = not cap["unknown"]
        return "ok", scrub(f"desktop képesség: piros: {'; '.join(cap['red']) or '-'}; zöld: {' · '.join(cap['ok']) or '-'}"), \
            "decided" if known else "undecidable"

    reps = d.doctor(agent=entry["agent"] if entry else None)
    want = entry["agent"] if entry else None
    r = next((x for x in reps if (x["agent"] == want if want else x["agent"].startswith("box "))), None)
    if r is None:
        return "ok", "nem mérhető (nincs riport)", "undecidable"
    # eldöntött: egészséges, vagy ismert hibákkal piros ÉS nincs nem-mérhető / függő sora
    known = r["health"] == "healthy" or (r["health"] == "unhealthy" and r.get("problems")
                                         and not r.get("unknown") and not r.get("pending"))
    return "ok", scrub(f"{r['health']}: {_lines(r)}"), "decided" if known else "undecidable"


def doctor_fix(entry: dict) -> tuple[str, str, None]:
    from fleet import doctor as d
    r = d.doctor(agent=entry["agent"], fix=True)[-1]
    return ("ok" if r["ok"] else "failed"), scrub(f"--fix után: {r['health']}: {_lines(r)}"), None


def bridge_install(entry: dict) -> tuple[str, str, None]:
    from fleet.bridge import install_bridge
    r = install_bridge(entry)
    return "ok", scrub(f"híd telepítve: {r.get('version', r) if isinstance(r, dict) else r}"), None


def _cause_holds(entry: dict, cause: str) -> bool:
    from fleet import dup, signals
    if cause == "login-renewed":
        from fleet.claude_auth import logged_in
        from fleet.install_checks import CLAUDE_BIN
        return logged_in(entry, claude_bin=CLAUDE_BIN, home=Path.home())
    if cause == "bridge-conflict-gone":
        from fleet.registry import load_agents, local_host
        procs = signals._proc_records()
        dups = [fe for fe, _ in dup.foreign_here(load_agents(), local_host(), procs) if fe["agent"] == entry["agent"]]
        return not signals.measure(entry, procs)["pollers"] and not dups
    return False


def unquarantine(entry: dict, cause: str | None) -> tuple[str, str, None]:
    if cause not in CAUSES:
        return "refused", scrub(f"ismeretlen vagy nem gépileg igazolható ok: {cause!r} — ember-kell"), None
    if not _cause_holds(entry, cause):
        return "failed", f"az ok ({cause}) gépileg NEM igazolódott — a karantén marad", None
    from fleet.reconcile import load_state, save_state, CORRUPT
    st = load_state(entry["agent"])
    if st is CORRUPT:
        return "failed", "az ágens állapotfájlja sérült — nem írom", None
    st["quarantined"], st["failed_postchecks"] = False, 0
    save_state(entry["agent"], st)
    return "ok", f"karantén feloldva (igazolt ok: {cause})", None


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "nincs-boot-id"


def probe(entry: dict) -> tuple[bool, str, str]:
    """Friss képesség-próba: (zöld?, boot-azonosító, összefoglaló). Zöld = fut a processz, a
    képesség-próbának nincs piros és nem-mérhető sora, legalább egy lépése zölden lefutott, és ha az
    ágensnek van ütemezése, a processz indulása UTÁN már lefutott egy tick (tick_signal: csak a tick
    írja). Különben piros — a menedzser a keretén belül újra futtathatja; a keret végén átadás/e-mail.
    Desktopon (saját gép, nincs always-on processz) a processz-jel helyett a session azonosítója."""
    from fleet import kepesseg, signals, tick_signal
    t = tick_signal.executed(entry)
    if kepesseg.is_desktop(entry):
        cap = _desktop_check(entry)
        sid, since = _session_id(entry), _session_started(entry)
        # ütemezett desktop-tagnál a tick a MOSTANI session indulása után kell (a session.id írása)
        ticked = t["owner"] == "none" or tick_signal.after(t, since)
        green = bool(sid) and not cap["red"] and not cap["unknown"] and bool(cap["ok"]) and ticked
        return green, f"desktop:{sid or '-'}", scrub(f"desktop; piros: {'; '.join(cap['red']) or '-'}; tick: {t['last_tick_at'] or '-'}")
    m = signals.measure(entry)
    proc = m["signals"]["process"]
    pid, started = proc.get("data", {}).get("pid"), proc.get("data", {}).get("started_s")
    cap = kepesseg.check(entry, Path.home())
    # a processz-azonosság a próba UTÁN is ugyanaz kell legyen (közben nem halt meg / indult újra)
    again = signals.measure(entry)["signals"]["process"]
    same = again.get("state") == "up" and again.get("data", {}).get("pid") == pid and again.get("data", {}).get("started_s") == started
    ticked = t["owner"] == "none" or tick_signal.after(t, started)
    green = proc.get("state") == "up" and bool(pid) and same and not cap["red"] and not cap["unknown"] and bool(cap["ok"]) and ticked
    boot = f"{_boot_id()}:{pid or '-'}:{started or '-'}"
    summary = scrub(f"processz {proc.get('state')}; piros: {'; '.join(cap['red']) or '-'}; "
                    f"nem mérhető: {'; '.join(cap['unknown']) or '-'}; zöld: {' · '.join(cap['ok']) or '-'}; "
                    f"friss tick az indulás óta: {'igen' if ticked else 'MÉG NINCS (' + str(t['last_tick_at']) + ')'}")
    return green, boot, summary


def _session_started(entry: dict) -> float | None:
    try:
        return (Path.home() / ".config" / entry["agent"] / "session.id").stat().st_mtime
    except OSError:
        return None


def _session_id(entry: dict) -> str:
    try:
        return (Path.home() / ".config" / entry["agent"] / "session.id").read_text().strip()[:80]
    except OSError:
        return ""


def report_now(entry: dict, tries: int = 3, wait_s: float = 61.0, sleep=None) -> bool:
    """Friss jelentés a központnak a próba UTÁN (a Worker ebből igazolja a zöldet, nem a végrehajtó
    szavából). A box-ritmuskorlát (1/60 s) miatt legfeljebb `tries`-szor próbál, `wait_s` szünettel."""
    import time as _t
    from fleet import flotta_now
    for i in range(tries):
        rc, _msg = flotta_now.report_now()
        if rc == 0:
            return True
        if i + 1 < tries:
            (sleep or _t.sleep)(wait_s)
    return False
