"""Minimal Google REST client (stdlib): the saved token, its refresh, one JSON call.

The token lives in `.secrets/google/token.json` (written by mentat_google_auth.py) and is never
printed. A refresh is the plain OAuth refresh-token request, so the calls themselves need no
Google library. MENTAT_GOOGLE_API points every service at one base (tests).
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import google_secrets as secrets

BASES = {"calendar": "https://www.googleapis.com", "drive": "https://www.googleapis.com",
         "gmail": "https://gmail.googleapis.com", "sheets": "https://sheets.googleapis.com"}


class GoogleError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__("HTTP %s %s" % (status, message))


class NotSignedIn(Exception):
    pass


def _expired(expiry):
    if not expiry:
        return True
    when = datetime.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when - datetime.timedelta(seconds=60) <= datetime.datetime.now(datetime.timezone.utc)


def access_token(root):
    path = secrets.folder(root) / "token.json"
    try:
        tok = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise NotSignedIn("not signed in to Google: run `python3 .mentat/bin/mentat_google_auth.py login` "
                          "(steps: reference/google.md)") from None
    if tok.get("token") and not _expired(tok.get("expiry")):
        return tok["token"]
    form = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": tok.get("refresh_token", ""),
                                   "client_id": tok.get("client_id", ""),
                                   "client_secret": tok.get("client_secret", "")}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(tok["token_uri"], data=form), timeout=30) as r:
            new = json.load(r)
    except (urllib.error.URLError, KeyError, ValueError) as e:
        raise NotSignedIn("the Google sign-in expired and could not be renewed (%s): run "
                          "`python3 .mentat/bin/mentat_google_auth.py login` again" % getattr(e, "code", e)) from None
    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=int(new.get("expires_in", 3600)))
    tok.update(token=new["access_token"], expiry=until.strftime("%Y-%m-%dT%H:%M:%SZ"))
    secrets.write(path, json.dumps(tok))
    return tok["token"]


def call(root, service, method, path, params=None, body=None):
    base = os.environ.get("MENTAT_GOOGLE_API") or BASES[service]
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + access_token(root), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = (json.load(e).get("error") or {}).get("message", "")
        except ValueError:
            msg = ""
        raise GoogleError(e.code, msg) from None
    except urllib.error.URLError as e:
        raise GoogleError(0, "unreachable: %s" % e.reason) from None
