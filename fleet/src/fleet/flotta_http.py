"""flotta-menedzser: a box JSON-hívásai a központi flotta-ellenőrzés felé (Mentat Admin `flotta` plugin).

    call(method, url, path, token, body, opener) -> (status | None, válasz-dict | None, info)

Egy helyen, hogy minden hívó ugyanúgy bánjon a tokennel és a hibával: a token csak a
`X-Mentat-Token` fejlécbe kerül, se kivételbe, se `info`-ba, se naplóba. Hálózati hiba:
`status` None, `info` a kivétel osztályneve. Csak https (http csak localhostra), átirányítás nélkül. A 4xx/5xx válasz törzsét beolvassuk (a 409
`code` mezője dönt), de a hívó soha nem írja ki nyersen.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request

TIMEOUT_S = 10


def _parse(raw: bytes) -> dict | None:
    try:
        d = json.loads(raw.decode() or "null")
    except (ValueError, UnicodeDecodeError):
        return None
    return d if isinstance(d, dict) else None


def call(method: str, url: str, path: str, token: str, body: dict | None = None,
         opener=None, timeout: float = TIMEOUT_S) -> tuple[int | None, dict | None, str]:
    # mint a box jelentése: https (http csak a saját gépre), és a token átirányítást nem követ
    from fleet.flotta_report import _OPENER, _url_ok
    if not _url_ok(url.rstrip("/")):
        return None, None, "nem https URL"
    opener = opener or _OPENER.open
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{url.rstrip('/')}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json", "X-Mentat-Token": token})
    try:
        with opener(req, timeout=timeout) as r:
            return r.status, _parse(r.read()), f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except OSError:
            raw = b""
        return e.code, _parse(raw), f"HTTP {e.code}"
    except (OSError, ValueError) as e:   # URLError, timeout, kapcsolat
        return None, None, type(e).__name__
