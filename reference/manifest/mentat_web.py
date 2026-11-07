#!/usr/bin/env python3
"""mentat_web.py — go live only on the USER's yes; check a web deploy the way the USER sees it.

    python3 .mentat/bin/mentat_web.py check URL [--cookie-file F | --service-token-env ID_VAR SECRET_VAR]
                                              [--expect 200] [--contains TEXT]
    python3 .mentat/bin/mentat_web.py deploy --approved "<the USER's yes, verbatim>" [--url URL]
                                              [check options] -- <deploy command…>

`deploy` runs the command only with a non-empty --approved (else NOT DEPLOYED, exit 2); a wrangler
deploy first checks every token permission the project needs (web/mentat_cf_token.py --for). Then
`LIVE <address>` + the protection check to run, or `NOT LIVE`; with --url or a credential: `check`.

One request with the USER's credential: an Access cookie (`CF_Authorization=…` in a file) or an
Access service token (two env variable NAMES; values never shown). No redirect is followed: a
sign-in redirect is not "up". `OK <status> …` (exit 0) or `FAIL <status> …` (exit 1); without a
credential it is a plain public check, after any web deploy.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None  # urllib then raises HTTPError with the 30x status


def _headers(a):
    h = {"User-Agent": "mentat-web-check"}
    if a.cookie_file:
        raw = pathlib.Path(a.cookie_file).read_text().strip()
        h["Cookie"] = raw if "=" in raw else "CF_Authorization=" + raw
    if a.service_token_env:
        id_var, secret_var = a.service_token_env
        cid, secret = os.environ.get(id_var), os.environ.get(secret_var)
        if not cid or not secret:
            raise SystemExit("FAIL setup: %s or %s is not set in the environment" % (id_var, secret_var))
        h["CF-Access-Client-Id"], h["CF-Access-Client-Secret"] = cid, secret
    return h


def _where(location):
    """Where a redirect points, without its query (it may carry a token)."""
    u = urllib.parse.urlsplit(location or "")
    return "%s://%s%s" % (u.scheme, u.netloc, u.path) if u.netloc else (u.path or "?")


def fetch(url, headers, timeout=20):
    """(status, body, redirect target or None)."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return e.code, "", _where(e.headers.get("Location")) if 300 <= e.code < 400 else None
    except (urllib.error.URLError, OSError) as e:
        return 0, "", "unreachable: %s" % getattr(e, "reason", e)


def check(a):
    status, body, redirect = fetch(a.url, _headers(a))
    target = _where(a.url)
    if status != a.expect:
        why = ("redirect to %s (not signed in? check it signed in: --cookie-file)" % redirect if redirect and status
               else redirect or "expected %d" % a.expect)
        print("FAIL %d %s — %s" % (status, target, why))
        return 1
    if a.contains and a.contains not in body:
        print("FAIL %d %s — %r missing from the page" % (status, target, a.contains))
        return 1
    print("OK %d %s%s" % (status, target, " — contains %r" % a.contains if a.contains else ""))
    return 0


def deploy(a):
    cmd = [c for c in a.command if c != "--"]
    if not cmd:
        raise SystemExit("usage: mentat_web.py deploy --approved \"<the USER's yes>\" -- <deploy command>")
    if not (a.approved or "").strip():
        print("NOT DEPLOYED: going live needs the USER's explicit yes (--approved \"<their words>\"); "
              "would run: %s" % " ".join(cmd))
        return 2
    print("approved: %s" % a.approved.strip())
    if "wrangler" in " ".join(cmd) and _preflight():
        return 2
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode:
        auth = re.search(r"\b(10000|403|Authentication error)\b", r.stdout + r.stderr) and " — a token permission: mentat_cf_token.py --check --for wrangler.toml names it"
        print("NOT LIVE: the deploy command failed (exit %d)%s" % (r.returncode, auth or ""))
        return r.returncode
    found = re.findall(r"https://[^\s'\"]+", r.stdout + r.stderr)
    url = a.url or next((u for u in found if ".workers.dev" in u or ".pages.dev" in u), found[0] if found else None)
    if not url:
        print("DEPLOYED, address unknown: pass --url so the report can say where it is live")
        return 0
    print("LIVE %s\nNEXT python3 .mentat/bin/mentat_done.py --protected %s   (unsigned: the sign-in)" % (url, url))
    if a.url or a.cookie_file or a.service_token_env:
        a.url = url
        return check(a)
    return 0


def _preflight():
    tool = next((d / "mentat_cf_token.py" for d in (HERE / "web", HERE.parent / "web") if (d / "mentat_cf_token.py").is_file()), None)
    r = tool and pathlib.Path("wrangler.toml").is_file() and subprocess.run(
        [sys.executable, str(tool), "--check", "--for", "wrangler.toml"], capture_output=True, text=True)
    if r and r.returncode:
        print("NOT DEPLOYED: the token is not ready for this project — %s" % (r.stdout.strip() or r.stderr.strip()))
    return bool(r and r.returncode)


def add_check_args(p):
    p.add_argument("--cookie-file", help="file holding CF_Authorization=… (or just its value)")
    p.add_argument("--service-token-env", nargs=2, metavar=("ID_VAR", "SECRET_VAR"),
                   help="names of the env variables holding the Access service token")
    p.add_argument("--expect", type=int, default=200)
    p.add_argument("--contains", help="text the page must contain (e.g. an item count)")


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="one request as the USER sees it")
    c.add_argument("url")
    add_check_args(c)
    d = sub.add_parser("deploy", help="run the deploy command only with the USER's explicit yes")
    d.add_argument("--approved", help="the USER's yes, verbatim (required to deploy)")
    d.add_argument("--url", help="the live address, also checked after the deploy")
    add_check_args(d)
    d.add_argument("command", nargs=argparse.REMAINDER)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    return check(a) if a.cmd == "check" else deploy(a)


if __name__ == "__main__":
    sys.exit(main())
