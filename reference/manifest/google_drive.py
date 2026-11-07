"""Drive/Sheets: share only with named people the contract allows (never "anyone with the link" or
a whole domain), write a sheet only when its rows pass the contract, and say who can see it."""
import csv
import io
import pathlib
import urllib.parse

import google_api as api
import google_people as people
import mentat_accept as accept
import mentat_accept_load as load

ROLES = ("reader", "commenter", "writer")


def _perms(root, fid):
    return api.call(root, "drive", "GET", "/drive/v3/files/%s/permissions" % urllib.parse.quote(fid, safe=""),
                    {"fields": "permissions(type,role,emailAddress,domain)"}).get("permissions", [])


def who_sees(root, fid):
    lines, named = [], []
    try:
        perms = _perms(root, fid)
    except api.GoogleError as e:
        return ["READ BACK: who sees it: unknown (%s; sign in with the drive scope to see it)" % e]
    for p in perms:
        if p.get("type") == "anyone":
            lines.append("WARNING: ANYONE with the link can open it (%s); ask the USER whether to switch it off "
                         "in the Share dialog" % p.get("role"))
        elif p.get("type") == "domain":
            lines.append("WARNING: everyone at %s can open it (%s)" % (p.get("domain"), p.get("role")))
        else:
            named.append("%s (%s)" % (p.get("emailAddress"), p.get("role")))
    return ["READ BACK: who sees it: %s" % (", ".join(named) or "only you")] + lines


def read(root, a):
    print("\n".join(who_sees(root, a.file)))
    return 0


def share(root, a):
    emails = [load.address(e) for e in a.email.split(",") if e.strip()]
    if a.role not in ROLES or not emails:
        print("usage: share FILE --email a@…[,b@…] --role %s --notify yes|no" % "|".join(ROLES))
        return 1
    code, lines = people.check(root, a.contract, {"bcc": emails, "visibility": "hidden", "role": a.role})
    if code:
        print("\n".join(lines))
        return code
    for e in emails:
        api.call(root, "drive", "POST", "/drive/v3/files/%s/permissions" % urllib.parse.quote(a.file, safe=""),
                 {"sendNotificationEmail": "true" if a.notify == "yes" else "false"},
                 {"type": "user", "role": a.role, "emailAddress": e})
    print("SHARED %s with %s as %s; notified by mail: %s" % (a.file, ", ".join(emails), a.role,
                                                           ", ".join(emails) if a.notify == "yes" else "nobody"))
    print("\n".join(who_sees(root, a.file)))
    return 0


def write(root, a):
    t, why = people.terms(root, a.contract)
    if t is None:
        print("NOT WRITTEN: %s" % why)
        return 2
    code, lines = accept.accept(root, a.contract, a.file)
    if code:
        print("NOT WRITTEN — the rows do not pass the contract:\n" + "\n".join(lines))
        return code
    rows = list(csv.reader(io.StringIO(pathlib.Path(a.file).read_text(encoding="utf-8"))))
    path = "/v4/spreadsheets/%s/values/%s" % (urllib.parse.quote(a.sheet, safe=""), urllib.parse.quote(a.range, safe=""))
    api.call(root, "sheets", "PUT", path, {"valueInputOption": "RAW"}, {"range": a.range, "values": rows})
    back = api.call(root, "sheets", "GET", path).get("values", [])
    print("WROTE %d rows (header included) to %s %s" % (len(rows), a.sheet, a.range))
    same = "the same as sent" if back == rows else "DIFFERENT from what was sent — check it before saying done"
    print("READ BACK: %d rows, %s" % (len(back), same))
    print("\n".join(who_sees(root, a.sheet)))
    return 0 if back == rows else 1
