#!/usr/bin/env python3
"""mentat_google.py — the one supported way to change something in Google Calendar, Gmail, Drive, Sheets.

    python3 .mentat/bin/mentat_google.py [--repo .] <service> <action> ...
      calendar create --title T --start ISO --end ISO [--tz Area/City] --notify none|externalOnly|all
                      [--contract ID --guests contract|a@…,b@…] [--guests-see-each-other] [--description D]
      calendar update EVENT_ID --notify … [--title/--start/--end/--description] [--contract ID] [--guests …]
      gmail send --contract ID --to a@…[,b@…] [--cc …] [--bcc …] --subject S --body-file F
      drive share FILE_ID --contract ID --email a@…[,b@…] --role reader|commenter|writer --notify yes|no
      sheets share SHEET_ID …(as drive share)    sheets write SHEET_ID --range 'Sheet1!A1' --file rows.csv --contract ID
      drive read FILE_ID                          who can open it

Every call that reaches other people needs the USER's approved contract (mentat_contract.py) and
passes mentat_accept.py's checks BEFORE it is made; then one line says what went out and who sees
it, and a READ BACK line says what Google now holds. Guests are hidden from each other unless the
contract says visible; the notification choice is never a default. The sign-in: mentat_google_auth.py.
Exit: 0 done, 1 red (nothing sent), 2 no approved contract, 3 ask the USER first, 4 not signed in.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import google_api as api  # noqa: E402
import google_calendar as cal  # noqa: E402
import google_drive as drive  # noqa: E402
import google_mail as mail  # noqa: E402
import mentat_contract_store as store  # noqa: E402


def _calendar(sub):
    for name in ("create", "update"):
        p = sub.add_parser(name)
        if name == "update":
            p.add_argument("event")
        p.add_argument("--notify", required=True, choices=["none", "externalOnly", "all"])
        for flag in ("--title", "--start", "--end", "--description", "--contract", "--guests"):
            p.add_argument(flag)
        p.add_argument("--tz", default="UTC")
        p.add_argument("--calendar", default="primary")
        p.add_argument("--guests-see-each-other", action="store_true")


def _share(sub):
    p = sub.add_parser("share")
    p.add_argument("file")
    p.add_argument("--contract")
    p.add_argument("--email", required=True)
    p.add_argument("--role", required=True, choices=list(drive.ROLES))
    p.add_argument("--notify", required=True, choices=["yes", "no"])


def parser():
    p = argparse.ArgumentParser(prog="mentat_google.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=".")
    svc = p.add_subparsers(dest="service", required=True)
    c = svc.add_parser("calendar").add_subparsers(dest="action", required=True)
    _calendar(c)
    g = svc.add_parser("gmail").add_subparsers(dest="action", required=True)
    s = g.add_parser("send")
    s.add_argument("--contract")
    for flag in ("--to", "--cc", "--bcc"):
        s.add_argument(flag)
    s.add_argument("--subject", required=True)
    s.add_argument("--body-file", required=True)
    d = svc.add_parser("drive").add_subparsers(dest="action", required=True)
    _share(d)
    d.add_parser("read").add_argument("file")
    sh = svc.add_parser("sheets").add_subparsers(dest="action", required=True)
    _share(sh)
    w = sh.add_parser("write")
    w.add_argument("sheet")
    w.add_argument("--range", required=True)
    w.add_argument("--file", required=True)
    w.add_argument("--contract")
    return p


ACTIONS = {("calendar", "create"): cal.create, ("calendar", "update"): cal.update,
           ("gmail", "send"): mail.send, ("drive", "share"): drive.share, ("sheets", "share"): drive.share,
           ("drive", "read"): drive.read, ("sheets", "write"): drive.write}


def main(argv=None):
    a = parser().parse_args(argv)
    root = pathlib.Path(a.repo)
    try:
        return ACTIONS[(a.service, a.action)](root, a)
    except api.NotSignedIn as e:
        print("NOT SIGNED IN: %s" % e)
        return 4
    except api.GoogleError as e:
        print("GOOGLE REFUSED (%s). Nothing more was done; report this to the USER as it is." % e)
        return 1
    except (store.ContractError, OSError, ValueError) as e:
        print("error: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
