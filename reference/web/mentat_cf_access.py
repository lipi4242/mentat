#!/usr/bin/env python3
"""Cloudflare Access in front of one Worker, through the API (not by clicking).

    mentat_cf_access.py ensure --worker NAME --email E [--email E2 ...] [--dry-run]
    mentat_cf_access.py check  --worker NAME

`ensure` creates a self-hosted Access application whose destination is the Worker
(`{"type": "worker", "worker_id": ...}`: its workers.dev and preview URLs) with one allow
policy for the given e-mails; if one exists it creates nothing (idempotent). `check` says
whether the Worker is protected. Exit: 0 ok / protected, 1 not protected or error,
2 the token lacks a permission (named). Token: CLOUDFLARE_API_TOKEN (env or .env).
API: POST /accounts/{account_id}/access/apps (permission: Access: Apps and Policies Edit).
"""
import argparse
import sys

from cf_api import CFError, account_id, call, env_value

PERM = {"workers": "Workers Scripts: Read", "access": "Access: Apps and Policies Edit"}


def worker_tag(token, acc, name):
    for s in call(token, "GET", "/accounts/%s/workers/scripts" % acc) or []:
        if s.get("id") == name:
            return s.get("tag")
    raise SystemExit("no Worker named %s in this account (deploy it first)" % name)


def find_app(token, acc, tag):
    for app in call(token, "GET", "/accounts/%s/access/apps" % acc) or []:
        if any(d.get("type") == "worker" and d.get("worker_id") == tag for d in app.get("destinations") or []):
            return app
    return None


def emails(app):
    return sorted({r["email"]["email"] for p in app.get("policies") or [] if isinstance(p, dict)
                   for r in p.get("include") or [] if isinstance(r, dict) and "email" in r})


def run(a):
    token = env_value("CLOUDFLARE_API_TOKEN")
    if not token:
        print("no CLOUDFLARE_API_TOKEN (env or .env): run mentat_cf_token.py first")
        return 2
    stage = "workers"
    try:
        acc = account_id(token)
        tag = worker_tag(token, acc, a.worker)
        stage = "access"
        app = find_app(token, acc, tag)
        if a.cmd == "check":
            print(("protected: %s (e-mails: %s)" % (app.get("name"), ", ".join(emails(app)) or "-"))
                  if app else "NOT protected: %s has no Access application" % a.worker)
            return 0 if app else 1
        if app:
            missing = sorted(set(a.email) - set(emails(app)))
            print("already protected: %s%s" % (app.get("name"), (
                "; not on its policy yet: %s (add them in the app's policy)" % ", ".join(missing)) if missing else ""))
            return 0
        body = {"name": "%s (mentat)" % a.worker, "type": "self_hosted",
                "destinations": [{"type": "worker", "worker_id": tag}],
                "policies": [{"name": "allowed people", "decision": "allow",
                              "include": [{"email": {"email": e}} for e in a.email]}]}
        if a.dry_run:
            print("would create Access app %s for %s" % (body["name"], ", ".join(a.email)))
            return 0
        call(token, "POST", "/accounts/%s/access/apps" % acc, body)
        print("protected: %s — next: check it as the USER (a signed-in request returns 200)" % body["name"])
        return 0
    except CFError as e:
        if e.status == 401:
            print("the token is invalid or expired: run mentat_cf_token.py again")
            return 2
        if e.auth():
            print("the token cannot do this (%s): add the permission %s to the token, then rerun"
                  % (e, PERM[stage]))
            return 2
        print("Cloudflare error: %s" % e)
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("ensure", "check"))
    ap.add_argument("--worker", required=True)
    ap.add_argument("--email", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "ensure" and not a.email:
        ap.error("ensure needs at least one --email")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
