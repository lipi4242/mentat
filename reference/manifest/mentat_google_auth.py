#!/usr/bin/env python3
"""mentat_google_auth.py — sign in to Google with the official library flow, never a home-made server.

    python3 .mentat/bin/mentat_google_auth.py [--repo .] import-client PATH   the downloaded Desktop-app JSON
    ... login [--scopes calendar,gmail,drive,sheets] [--timeout 300] [--no-browser --port 8765]
    ... login --remote [--port 8765]     the browser is on another machine: prints ONE link (exit 3)
    ... finish "<the address the browser ended on>"                      second step of --remote
    ... status

`login` runs google-auth-oauthlib's InstalledAppFlow.run_local_server on this machine, waiting at
most --timeout seconds. --no-browser prints the link instead of opening it (for an SSH tunnel:
`ssh -L PORT:localhost:PORT <this machine>`). --remote needs no server and no tunnel: the USER
opens the link, allows access, and sends back the address their browser shows (the page itself
does not load — that is expected); it holds a one-time code that `finish` uses within 10 minutes.
Exit: 0 signed in, 1 failed, 3 waiting for the USER, 4 a file or the library is missing.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import google_secrets as secrets  # noqa: E402
import google_signin as signin  # noqa: E402

def import_client(a, d):
    src = pathlib.Path(a.path)
    doc = json.loads(src.read_text(encoding="utf-8"))
    if "installed" not in doc:
        print("NOT USABLE: this is not a Desktop app client. In the console create Credentials → OAuth "
              "client ID → Application type: Desktop app, download its JSON and give me that file.")
        return 1
    secrets.write(d / "client.json", json.dumps(doc))
    print("saved the OAuth client to %s/client.json (0600, git-ignored); the downloaded copy at %s can "
          "be deleted. If it was ever pasted into a chat, make a new client secret in the console." % (secrets.REL, src))
    return 0


def status(a, root, d):
    tok = d / "token.json"
    if not tok.exists():
        print("not signed in (%s/token.json missing)" % secrets.REL)
        return 1
    print("signed in; scopes: %s" % ", ".join(json.loads(tok.read_text()).get("scopes") or ["?"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_google_auth.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import-client").add_argument("path")
    lg = sub.add_parser("login")
    lg.add_argument("--scopes", default="calendar,gmail,drive,sheets")
    lg.add_argument("--timeout", type=int, default=300)
    lg.add_argument("--port", type=int, default=0)
    lg.add_argument("--no-browser", action="store_true")
    lg.add_argument("--remote", action="store_true")
    sub.add_parser("finish").add_argument("address")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "login" and (a.remote or a.no_browser) and not a.port:
        a.port = 8765
    root = pathlib.Path(a.repo)
    try:
        d = secrets.ensure(root)
        return {"import-client": import_client, "login": signin.login, "finish": signin.finish, "status": status}[a.cmd](
            *((a, d) if a.cmd == "import-client" else (a, root, d)))
    except secrets.SecretsError as e:
        print(e)
        return 1
    except (OSError, ValueError, KeyError) as e:
        print("error: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
