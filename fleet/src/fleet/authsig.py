"""Az ötödik jel: a Claude-bejelentkezés él-e. 2026-09-24..10-01 között három
boxon járt le a login, és mind a négy klasszikus jel
zöld maradt: a processz fut, a híd injektál, a health frissül — csak minden
bejövőre egy szintetikus „Login expired · Please run /login" megy vissza, a
pane-be, és a tick sem fut. A tulajdonos a Telegramon vette észre, napokkal később.

A nyom a transzkriptben strukturált: egy assistant-rekord
`"error":"authentication_failed"` + `"isApiErrorMessage":true` mezőkkel. A
gyógyulás nyoma egy KÉSŐBBI valódi assistant-üzenet. Restart nem segít; a
műveletek közül csak riasztás jár érte.
"""
from __future__ import annotations
import os
import re
from datetime import datetime

from fleet.signals import Signal, UNKNOWN, transcript_path, _TS_RE

_AUTH_FAIL = '"error":"authentication_failed"'
_ASSISTANT = '"type":"assistant"'
_API_ERROR = '"isApiErrorMessage":true'
_LOGIN_HINT = "claude auth login   (azon a boxon, az ágens userével; a többi ágens ugyanazon a fiókon vele gyógyul)"


def auth_events(lines: list[str]) -> list[tuple[float, str]]:
    """Pure: (epoch, 'auth_failed'|'ok') az assistant-rekordokból. A többi
    API-hiba (túlterhelés, hálózat) nem 'ok' és nem 'auth_failed' — kimarad."""
    out = []
    for line in lines:
        if _ASSISTANT not in line:
            continue
        t = _TS_RE.search(line)
        if not t:
            continue
        try:
            when = datetime.fromisoformat(t.group(1).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if _AUTH_FAIL in line:
            out.append((when, "auth_failed"))
        elif _API_ERROR not in line:
            out.append((when, "ok"))
    return out


def auth_verdict(events: list[tuple[float, str]]) -> tuple[str, str, dict]:
    """Pure. Az UTOLSÓ assistant-esemény dönt: 'expired' ha az auth-hiba,
    'ok' ha valódi üzenet; 'unknown' ha nincs esemény a vizsgált szeletben."""
    if not events:
        return UNKNOWN, "nincs assistant-üzenet a transzkript vizsgált részében", {}
    when, last = events[-1]
    stamp = datetime.fromtimestamp(when).strftime("%m-%d %H:%M")
    if last == "auth_failed":
        first, n = when, 0
        for e in reversed(events):          # a záró hibasorozat: mióta, hány
            if e[1] != "auth_failed":
                break
            first, n = e[0], n + 1
        return "expired", (f"Login expired {datetime.fromtimestamp(first).strftime('%m-%d %H:%M')} óta, "
                           f"{n} üzenet kapott hibát — {_LOGIN_HINT}"), {"since_s": first, "failed": n}
    return "ok", f"utolsó valódi válasz {stamp}", {"last_ok_s": when}


#: Meddig bizonyíték egy sikeres `claude auth status` (claude_auth.ensure_auth),
#: amíg az ágens még egyetlen választ sem adott.
PROOF_TTL_S = 24 * 3600


def proven_login(entry: dict, why: str, now: float | None = None) -> Signal:
    """Friss ágensnél nincs transzkript / válasz: a login még nem volt
    használva, tehát nem is bukhatott el. A telepítéskori `claude auth status`
    (a unit szemével) az egyetlen bizonyíték — 24 óráig; utána unknown."""
    import time
    from pathlib import Path
    from fleet.claude_auth import proof_path
    try:
        age = (now or time.time()) - float(proof_path(entry, Path.home()).read_text().strip())
    except (OSError, ValueError):
        return Signal("auth", UNKNOWN, why)
    if age > PROOF_TTL_S:
        return Signal("auth", UNKNOWN, why)
    return Signal("auth", "ok", f"{why}; a `claude auth status` (a unit szemével) {int(age // 60)} perce OK")


def auth_signal(entry: dict, sid: str | None, scan_bytes: int = 8 * 1024 * 1024) -> Signal:
    if not sid:
        return proven_login(entry, "nincs session.id")
    tp = transcript_path(entry, sid)
    if tp is None:
        return proven_login(entry, "nincs transzkript")
    try:
        with tp.open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - scan_bytes))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return Signal("auth", UNKNOWN, "transzkript nem olvasható")
    state, detail, data = auth_verdict(auth_events(tail))
    if state == UNKNOWN:
        return proven_login(entry, detail)
    return Signal("auth", state, detail, data)
