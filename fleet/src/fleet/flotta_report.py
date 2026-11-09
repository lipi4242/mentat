"""11-07: a box jelentése a központi flotta-ellenőrzésnek (a Mentat Admin `flotta` pluginja).

    config() -> (url, token) | None          ~/.config/fleet/flotta.env: FLOTTA_URL + FLOTTA_TOKEN;
                                             nincs fájl = a funkció ki van kapcsolva (a doctor mondja)
    check_key(line) -> str                   a piros sor stabil kulcsa (a worker ezzel dedupe-ol);
                                             11-08: `todo-ebresztes` a híd todo-ébresztésének
    build(state, agents, host, home) -> dict a jelentés: box, flotta-verzió, kiadás, ágensek eredménye
    maybe_report(state, agents, host, now) -> 'sent' | 'fresh' | 'failed' | 'off'
    force()                                  a következő hívás a 10 perces ritmus előtt is küld
    status(now) -> (problémák, figyelmeztetések, tények, nem-mérhető)   a doctor box-sorához

flotta-menedzser: a jelentés a végrehajtó önpróbáját is viszi (`repair`), a válasz `coverage`-ét az állapotfájl
őrzi (flotta_coverage.lines → doctor). Az elavult jelentés PIROS (a Worker nem érhető el: a box nem
jelent, a végrehajtó nem léphet), és a helyi tartalék-fájl (flotta_coverage.UNREACHABLE) is megíródik.

A hálózati hiba soha nem töri el a reconcile-t: korlátos idő (TIMEOUT_S), a hiba csak az
állapotfájlba és a naplóba kerül (`~/.config/fleet/state/flotta-report.json`), a doctor
„elavult”-at mutat, a képesség-riasztás pedig a fájl-tartalékba megy (kepesseg_riaszt.py).
A token értéke sehol nem jelenik meg: se naplóban, se hibaüzenetben, se a doctorban.
"""
from __future__ import annotations
import calendar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from fleet import CONFIG_DIR, __version__, alerts, release_lag

ENV_PATH = CONFIG_DIR / "flotta.env"
STATE = CONFIG_DIR / "state" / "flotta-report.json"
REPORT_S = 600          # 10 percenként (a reconcile 5 percenként fut)
STALE_S = 1800          # ennyi sikeres jelentés nélkül a doctor „elavult”-at mond
TIMEOUT_S = 10

# (minta, kulcs): az első egyező nyer. A sorok a kepesseg.py és az essentials.py saját sorai.
# A kulcsok a worker zárt listája (flotta/types.ts CHECKS); a worker az ismeretlent `egyeb`-re teszi.
_KEYS = ((r"^küldés", "kuldes"), (r"^todo-ébresztés", "todo-ebresztes"), (r"^todo", "todo"),
         (r"^saját állapot", "allapot"), (r"^git", "git"),
         (r"^képesség:", "repo"), (r"^tick-kapu:", "tick"), (r"TILTVA", "kapu"), (r"nincs TELEGRAM_BOT_TOKEN", "token"),
         (r"token nélkül", "nema-kuldes"))


def check_key(line: str) -> str:
    for pat, key in _KEYS:
        if re.search(pat, line):
            return key
    return "egyeb"


def _url_ok(url: str) -> bool:
    """https kell; http csak a saját gépre (helyi admin-fejlesztés, tesztek)."""
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and bool(p.hostname) or (p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost", "::1"))


def config() -> tuple[str, str] | None:
    env = alerts._env_from_file(ENV_PATH)
    url, tok = env.get("FLOTTA_URL", "").rstrip("/"), env.get("FLOTTA_TOKEN", "")
    return (url, tok) if _url_ok(url) and tok else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A token-fejléc nem követhet átirányítást: a 3xx hiba, nem új cél."""

    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=1))


def force() -> None:
    d = _load()
    d["due"] = True
    _save(d)


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def build(state: dict, agents: list[str], host: str, home: Path | None = None) -> dict:
    lag, _unk, _fact = release_lag.check(home)
    out = []
    entries = _entries()
    for a in agents:
        r = state.get(a)
        if not isinstance(r, dict):
            continue
        row = {"agent": a, "measured_at": _iso(float(r.get("at", 0))),
               "red": [{"check": check_key(x), "detail": x[:500]} for x in r.get("red", [])],
               "unknown": [x[:500] for x in r.get("unknown", [])][:50], "ok": [x[:500] for x in r.get("ok", [])][:50]}
        _with_tick(row, entries.get(a), home)
        out.append(row)
    return {"box": host, "fleet_version": __version__, "sent_at": _iso(time.time()),
            "release": {"here": release_lag.describe() or None, "latest": release_lag.cached_latest(home), "lag": lag},
            "agents": out, "repair": _repair()}


EXPIRY_WARN_S = 14 * 86400
_EXPIRY = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


def _expiry(body: bytes) -> str | None:
    """A token lejárata a válaszból (csak az alakja ellenőrzött dátum kerül az állapotba)."""
    try:
        v = json.loads(body or b"{}").get("token_expires_at")
    except (ValueError, AttributeError):
        return None
    return v[:19] if isinstance(v, str) and _EXPIRY.match(v) else None


REJECTED_HTTP = (400, 401, 403, 409)
_REJECT_CODES = ("invalid", "box-mismatch", "cross-box", "too-large")


def _reject_code(e) -> str:
    """A központ zárt elutasítás-kódja a válaszból; más szöveg nem kerül át."""
    try:
        code = json.loads(e.read(2048) or b"{}").get("code")
    except (ValueError, OSError, AttributeError):
        return ""
    return code if code in _REJECT_CODES else ""


def _repair() -> dict:
    try:
        from fleet import flotta_coverage
        return flotta_coverage.repair_probe()
    except Exception as e:  # noqa: BLE001 — a próba hibája piros próba, nem törött jelentés
        return {"ok": False, "detail": f"önpróba-hiba: {type(e).__name__}"}


def _entries() -> dict:
    try:
        from fleet import essentials
        return {e["agent"]: e for e in essentials.local_agents()}
    except Exception:  # noqa: BLE001 — registry nélkül nincs tick-nyom, a jelentés megy
        return {}


def _process_started(entry: dict) -> float | None:
    """Az ágens processzének indulása (box: a processz-jel; desktop: a session.id írása). None: nem mérhető."""
    try:
        from fleet import kepesseg
        if kepesseg.is_desktop(entry):
            return (Path.home() / ".config" / entry["agent"] / "session.id").stat().st_mtime
        from fleet import signals
        return signals.measure(entry)["signals"]["process"].get("data", {}).get("started_s")
    except Exception:  # noqa: BLE001 — nem mérhető: nincs türelmi idő, a régi szabály dönt
        return None


def _with_tick(row: dict, entry: dict | None, home: Path | None) -> None:
    """flotta-menedzser: az utolsó LEFUTOTT tick (csak a tick írja) kívülről látható; a régi nyom piros `tick`."""
    if entry is None:
        return
    from fleet import tick_signal
    try:
        t = tick_signal.executed(entry, home)
    except Exception:  # noqa: BLE001
        return
    row["tick"] = tick_signal.public(t)
    from fleet import kepesseg
    row["desktop"] = kepesseg.is_desktop(entry)   # a Worker ezt és a box fajtáját is nézi (a szigorúbb nyer)
    started = _process_started(entry)
    v = tick_signal.verdict(t, started)
    if v == "pending":   # friss indulás: az első tickig nem incidens (különben minden restart után hamis riasztás)
        until = tick_signal.grace_until(t, started)
        row["unknown"].append(f"tick: friss indulás, az első tickre vár ({_iso(until)}-ig)" if until else "tick: az első tickre vár")
    elif v == "red" and t["age_s"] is not None and (started is None or (t["_at"] or 0) > started):
        row["red"].append({"check": "tick", "detail": f"az utolsó lefutott tick {t['age_s'] // 60} perce volt "
                           f"(periódus {t['period_s'] // 60} perc, ütemező: {t['owner']})"})
    elif v == "red":
        row["red"].append({"check": "tick", "detail": f"nincs tick-nyom az indulás óta (data/state/last-tick.json), pedig az ágens "
                           f"ütemezett ({t['owner']}, periódus {t['period_s'] // 60} perc) — a loop halott, vagy a tick nem ír nyomot"})


def send(report: dict, cfg: tuple[str, str], opener=None, *, body: dict | None = None) -> tuple[bool, str, str | None]:
    """`body`-ba (ha adott) a válasz JSON-ja kerül (a coverage miatt); a törzset nem írjuk ki."""
    url, token = cfg
    req = urllib.request.Request(f"{url}/api/flotta/v1/report", data=json.dumps(report).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Mentat-Token": token})
    try:
        with (opener or _OPENER.open)(req, timeout=TIMEOUT_S) as r:
            ok = 200 <= r.status < 300
            raw = r.read(256 * 1024) if ok else b""
            if body is not None and raw:
                try:
                    d = json.loads(raw.decode() or "{}")
                    body.update(d if isinstance(d, dict) else {})
                except (ValueError, UnicodeDecodeError, AttributeError):
                    pass
            return ok, f"HTTP {r.status}", _expiry(raw) if ok else None
    except urllib.error.HTTPError as e:   # a válasz törzsét nem írjuk ki: csak a kód (és a zárt elutasítás-kód)
        return False, f"HTTP {e.code}" + (f" {_reject_code(e)}" if e.code in REJECTED_HTTP else ""), None
    except (OSError, ValueError) as e:    # URLError, timeout, kapcsolat
        return False, type(e).__name__, None


def maybe_report(state: dict, agents: list[str], host: str | None, now: float | None = None,
                 home: Path | None = None, opener=None) -> str:
    now = time.time() if now is None else now
    cfg = config()
    if cfg is None or not host:
        return "off"
    st = _load()
    if not st.get("due") and now - float(st.get("last_attempt", 0)) < REPORT_S:
        return "fresh" if st.get("last_ok", 0) >= st.get("last_attempt", 0) else "failed"
    resp: dict = {}
    try:
        ok, info, expires = send(build(state, agents, host, home), cfg, opener, body=resp)
    except Exception as e:  # noqa: BLE001 — a jelentés hibája a reconcile-t nem törheti el
        ok, info, expires = False, type(e).__name__, None
    st.update({"last_attempt": now, "due": False, "last_info": info})
    if ok:
        st["last_ok"] = now
        if expires:
            st["token_expires_at"] = expires
        st["coverage"] = resp.get("coverage") if isinstance(resp.get("coverage"), dict) else None
    _save(st)
    return "sent" if ok else "failed"


def status(now: float | None = None) -> tuple[list[str], list[str], list[str], list[str]]:
    """(problémák, figyelmeztetések, tények, nem-mérhető) a doctor box-sorához."""
    now = time.time() if now is None else now
    if config() is None:
        return [], [f"jelentés: kikapcsolva — nincs {ENV_PATH} (FLOTTA_URL + FLOTTA_TOKEN); a képesség-hiba "
                    "így csak a fájl-tartalékba kerül, senkihez nem jut el"], [], []
    st = _load()
    ok = float(st.get("last_ok", 0))
    info = str(st.get("last_info", ""))
    if st.get("last_attempt") and float(st["last_attempt"]) > ok and info.split(" ")[1:2] and \
            info.split(" ")[1].isdigit() and int(info.split(" ")[1]) in REJECTED_HTTP:
        # 11-08: az elutasított jelentés nem „elavult”, hanem hiba — a központ nem látja a boxot
        why = {"401": "a box-token érvénytelen vagy visszavont — új token az Adminban (POST …/boxes/<box>/token)",
               "409": "egy ágens másik boxhoz tartozik — áthelyezés az Adminban (POST …/agents/<név>/release)"}
        return [f"jelentés: a központ ELUTASÍTOTTA ({info}) — {why.get(info.split(' ')[1], 'a jelentés alakja nem megfelelő')}; "
                "amíg így marad, a box a központnak néma"], [], [], []
    if not st.get("last_attempt"):
        return [], [], [], ["jelentés: ismeretlen — még nem próbált jelenteni (a következő reconcile küldi)"]
    from fleet import flotta_coverage
    if info.startswith("HTTP 429") and now - float(st["last_attempt"]) <= STALE_S:
        # a ritmuskorlát nem elérhetetlenség: a központ válaszolt, a következő kör újra küld
        return [], [f"jelentés: ritmuskorlát (HTTP 429) — a következő körben újra küld"], [], []
    if now - ok > STALE_S:
        last = _iso(ok) if ok else "soha"
        flotta_coverage.unreachable(st, now)
        return [f"jelentés: elavult — a Worker nem érhető el; utolsó sikeres: {last}, utolsó hiba: "
                f"{st.get('last_info', '?')} (tartalék: {flotta_coverage.UNREACHABLE}); a menedzserek "
                "végrehajtója így nem léphet"], [], [], []
    flotta_coverage.clear()
    probs, warn = flotta_coverage.lines(st.get("coverage"))
    exp = st.get("token_expires_at")
    if isinstance(exp, str):
        try:
            left = calendar.timegm(time.strptime(exp[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")) - now
        except ValueError:
            left = None
        if left is not None and left < EXPIRY_WARN_S:
            warn.append(f"jelentés: a box-token {exp[:10]}-kor lejár — forgasd: POST /api/flotta/v1/boxes/<box>/token "
                        "(admin), és írd át a flotta.env-et")
    return probs, warn, [f"jelentés: friss ({int((now - ok) // 60)} perce, {st.get('last_info', '')})"], []
