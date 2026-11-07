"""Minimal Cloudflare API client (stdlib). The token is read from the environment or the
project's .env and is never printed. The endpoint: CLOUDFLARE_API_BASE_URL (the variable wrangler
honours: a gateway, a proxy, a mock), then CLOUDFLARE_API_BASE (older name), then the public API."""
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.cloudflare.com/client/v4"


class CFError(Exception):
    def __init__(self, status, errors):
        self.status, self.errors = status, errors or []
        super().__init__("HTTP %s %s" % (status, "; ".join(
            "%s %s" % (e.get("code"), e.get("message")) for e in self.errors)))

    def auth(self):
        """A missing permission or a bad token, not a broken request."""
        return self.status in (401, 403) or any(e.get("code") in (10000, 9109, 10001) for e in self.errors)


def env_value(key, path=".env"):
    if os.environ.get(key):
        return os.environ[key]
    p = pathlib.Path(path)
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            k, _, v = line.strip().partition("=")
            if k.removeprefix("export ").strip() == key and v:
                return v.strip().strip("'\"")
    return None


def _base():
    """The endpoint the token may go to: the public API, a loopback mock, or a host a person
    allowed in the environment (MENTAT_CF_API_ALLOW_HOST; the guard denies setting these three
    variables from a command). Anything else is refused: the token is not sent."""
    base = (os.environ.get("CLOUDFLARE_API_BASE_URL") or os.environ.get("CLOUDFLARE_API_BASE") or BASE).rstrip("/")
    u = urllib.parse.urlsplit(base)
    host = (u.hostname or "").lower()
    allowed = {h.strip().lower() for h in os.environ.get("MENTAT_CF_API_ALLOW_HOST", "").split(",") if h.strip()}
    if (u.scheme == "https" and host == "api.cloudflare.com") or host in ("127.0.0.1", "localhost", "::1") \
            or host in allowed:
        return base
    raise SystemExit("the Cloudflare token is not sent to %s: only api.cloudflare.com, a loopback address, or a "
                     "host a person allowed (MENTAT_CF_API_ALLOW_HOST in the environment)" % (host or base))


def call(token, method, path, body=None):
    base = _base()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            doc = json.load(e)
        except ValueError:
            doc = {}
        raise CFError(e.code, doc.get("errors")) from None
    if not doc.get("success", True):
        raise CFError(200, doc.get("errors"))
    return doc.get("result")


def account_id(token):
    """CLOUDFLARE_ACCOUNT_ID, else the token's only account."""
    acc = env_value("CLOUDFLARE_ACCOUNT_ID")
    if acc:
        return acc
    accounts = call(token, "GET", "/accounts") or []
    if len(accounts) != 1:
        raise SystemExit("set CLOUDFLARE_ACCOUNT_ID in .env (the token sees %d accounts)" % len(accounts))
    return accounts[0]["id"]
