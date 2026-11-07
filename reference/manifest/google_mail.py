"""Gmail send: several outside recipients see each other only if the contract says so; a private
group mail (audience.visibility = hidden) goes in Bcc; otherwise ask first. Read back after."""
import base64
import email.message
import pathlib

import google_api as api
import google_people as people
import mentat_accept_load as load


def _split(value):
    return [load.address(p) for p in (value or "").split(",") if p.strip()]


def _headers(back):
    return {h["name"]: h["value"] for h in (back.get("payload") or {}).get("headers", [])}


def send(root, a):
    to, cc, bcc = _split(a.to), _split(a.cc), _split(a.bcc)
    if not to + cc + bcc:
        print("usage: gmail send needs --to, --cc or --bcc")
        return 1
    t, why = people.terms(root, a.contract)
    if t is None:
        print("NOT SENT: %s" % why)
        return 2
    me = api.call(root, "gmail", "GET", "/gmail/v1/users/me/profile")["emailAddress"].lower()
    own = me.split("@")[-1]
    shown_outside = [p for p in dict.fromkeys(to + cc) if p.split("@")[-1] != own]
    moved = False
    if len(to + cc) > 1 and len(shown_outside) > 1:
        vis = (t.get("audience") or {}).get("visibility")
        if vis == "hidden":
            to, cc, bcc, moved = [], [], to + cc + bcc, True
        elif vis != "visible":
            print("ASK the USER first: %d outside recipients would see each other's addresses (%s). A private "
                  "group mail: draft the contract again with audience.visibility = hidden (everyone goes in Bcc); "
                  "if they should see each other: = visible. Nothing was sent." % (len(shown_outside), ", ".join(shown_outside)))
            return 3
    text = pathlib.Path(a.body_file).read_text(encoding="utf-8")
    plan = {"to": to, "cc": cc, "bcc": bcc, "subject": a.subject, "body": text}
    code, lines = people.check(root, a.contract, plan)
    if code:
        print("\n".join(lines))
        return code
    msg = email.message.EmailMessage()
    for name, group in (("To", to), ("Cc", cc), ("Bcc", bcc)):
        if group:
            msg[name] = ", ".join(group)
    msg["Subject"] = a.subject
    msg.set_content(text)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = api.call(root, "gmail", "POST", "/gmail/v1/users/me/messages/send", body={"raw": raw})
    hidden = "" if len(to + cc) > 1 else ", who cannot see each other"
    print("SENT %r from %s to %d recipients%s: visible %s; Bcc %d%s"
          % (a.subject, me, len(set(to + cc + bcc)), hidden, ", ".join(to + cc) or "nobody", len(bcc),
             " (moved to Bcc: the contract says a private group mail)" if moved else ""))
    back = _headers(api.call(root, "gmail", "GET", "/gmail/v1/users/me/messages/" + sent["id"],
                             [("format", "metadata")] + [("metadataHeaders", h) for h in ("To", "Cc", "Bcc", "Subject")]))
    print("READ BACK: Gmail has %r, To: %s, Cc: %s, Bcc: %s" % (back.get("Subject"), back.get("To", "-"),
                                                                back.get("Cc", "-"), back.get("Bcc", "-")))
    return 0
