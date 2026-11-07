"""The Google sign-in flows behind mentat_google_auth.py: the library's local server with a bounded
wait, or the two-step remote sign-in (a link, then the address the browser ended on). Only
google-auth-oauthlib does OAuth here; no callback server of our own."""
import json
import os
import time

import google_secrets as secrets

SCOPES = {"calendar": "https://www.googleapis.com/auth/calendar.events",
          "gmail": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.metadata",
          "drive": "https://www.googleapis.com/auth/drive",
          "sheets": "https://www.googleapis.com/auth/spreadsheets"}
INSTALL = ("MISSING: the Google sign-in library. Install it once: `python3 -m pip install --user "
           "google-auth-oauthlib` (in a virtual environment: `pip install google-auth-oauthlib`), then run this again.")
PENDING_SECONDS = 600


def _flow_module():
    try:
        from google_auth_oauthlib import flow
    except ImportError:
        print(INSTALL)
        raise SystemExit(4)
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")  # the USER may untick a box: report, do not crash
    return flow


def _client(d):
    path = d / "client.json"
    if not path.exists():
        print("MISSING: %s. Ask the USER for the downloaded OAuth client file (a file, not pasted into "
              "the chat), then `import-client <path>`." % path)
        raise SystemExit(4)
    return str(path)


def _save(a, root, d, creds, services):
    secrets.write(d / "token.json", creds.to_json())
    granted = json.loads(creds.to_json()).get("scopes") or []
    note = secrets.connector_note(root, services, granted)
    print("SIGNED IN: Google %s; the sign-in is in %s/token.json (0600), the note in %s."
          % (", ".join(services), secrets.REL, note.relative_to(root)))
    return 0


def login(a, root, d):
    services = [s.strip() for s in a.scopes.split(",") if s.strip()]
    scopes = " ".join(SCOPES[s] for s in services).split()
    flow = _flow_module()
    if a.remote:
        f = flow.Flow.from_client_secrets_file(_client(d), scopes, redirect_uri="http://localhost:%d/" % a.port)
        url, state = f.authorization_url(access_type="offline", prompt="consent")
        secrets.write(d / "pending.json", json.dumps({
            "state": state, "code_verifier": f.code_verifier, "scopes": scopes, "services": services,
            "redirect_uri": "http://localhost:%d/" % a.port, "expires": time.time() + PENDING_SECONDS}))
        print("STEP: send the USER this link: %s\nAfter they allow access, their browser goes to a page that "
              "does not load — that is expected. Ask them to copy the whole address from the address bar and "
              "send it, then run `finish \"<that address>\"` (within 10 minutes)." % url)
        return 3
    f = flow.InstalledAppFlow.from_client_secrets_file(_client(d), scopes)
    if a.no_browser:
        print("WAITING up to %d s. If the browser is on another computer, first: ssh -L %d:localhost:%d "
              "<this machine>, then open the link below there." % (a.timeout, a.port, a.port), flush=True)
    else:
        print("WAITING up to %d s: a browser window opens; sign in and allow access." % a.timeout, flush=True)
    start = time.time()
    try:
        creds = f.run_local_server(port=a.port, open_browser=not a.no_browser, timeout_seconds=a.timeout,
                                   authorization_prompt_message="Open this link: {url}",
                                   success_message="Done. You can close this tab and go back to the chat.")
    except Exception as e:  # the library has no single timeout error type
        waited = time.time() - start
        why = ("nobody signed in within %d s" % a.timeout if waited >= a.timeout - 1 or isinstance(e, AttributeError)
               else "%s" % type(e).__name__)
        print("NOT SIGNED IN: %s. Nothing was saved; run login again when the USER is ready." % why)
        return 1
    return _save(a, root, d, creds, services)


def finish(a, root, d):
    try:
        p = json.loads((d / "pending.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("NOTHING PENDING: run `login --remote` first.")
        return 1
    if time.time() > p.get("expires", 0):
        (d / "pending.json").unlink()
        print("EXPIRED: the link is older than 10 minutes; start again with `login --remote`.")
        return 1
    f = _flow_module().Flow.from_client_secrets_file(_client(d), p["scopes"], redirect_uri=p["redirect_uri"],
                                                    state=p["state"], code_verifier=p["code_verifier"])
    try:
        f.fetch_token(authorization_response=a.address.strip().replace("http://", "https://", 1))
    except Exception as e:  # oauthlib raises many kinds; none of them carries a secret
        print("NOT SIGNED IN: the address was not accepted (%s); start again with `login --remote`." % type(e).__name__)
        return 1
    (d / "pending.json").unlink()
    return _save(a, root, d, f.credentials, p["services"])


