"""Calendar create/update: guests hidden from each other unless the contract says otherwise, the
notification choice explicit, the guest list checked before the call, the event read back after."""
import urllib.parse

import google_api as api
import google_people as people
import mentat_accept_load as load


def _when(value, tz):
    return {"date": value} if len(value) == 10 else {"dateTime": value, "timeZone": tz}


def _guests(root, a):
    if not a.guests:
        return None
    if a.guests == "contract":
        return people.eligible(root, a.contract)
    return [load.address(g) for g in a.guests.split(",") if g.strip()]


def _emails(ev):
    return [x.get("email", "") for x in ev.get("attendees") or []]


def notified(ev, notify):
    guests = _emails(ev)
    if notify == "none" or not guests:
        return "nobody"
    if notify == "all":
        return ", ".join(guests)
    own = (ev.get("organizer") or {}).get("email", "").split("@")[-1]
    return ", ".join(g for g in guests if g.split("@")[-1] != own) or "nobody (every guest is in your domain)"


def seen(ev):
    guests = _emails(ev)
    if not guests:
        return "no guests"
    see = "see each other" if ev.get("guestsCanSeeOtherGuests", True) else "cannot see each other"
    return "%d guests (%s), who %s" % (len(guests), ", ".join(guests), see)


def gate(root, a, ev):
    """(code, lines) for the event as it would be after the call."""
    guests = _emails(ev)
    if not guests:
        return 0, []
    if a.guests_see_each_other:
        t, why = people.terms(root, a.contract)
        if t is None:
            return 2, ["NOT SENT: %s" % why]
        if (t.get("audience") or {}).get("visibility") != "visible":
            return 1, ["NOT SENT: the contract does not say the guests may see each other; ask the USER "
                       "and draft it again with audience.visibility = visible"]
    plan = {"guests": guests, "guestsCanSeeOtherGuests": bool(ev.get("guestsCanSeeOtherGuests")),
            "title": ev.get("summary", ""), "description": ev.get("description", "")}
    return people.check(root, a.contract, plan)


def _path(a, eid=""):
    return "/calendar/v3/calendars/%s/events%s" % (urllib.parse.quote(a.calendar, safe=""),
                                                  "/" + urllib.parse.quote(eid, safe="") if eid else "")


def _report(root, a, verb, ev):
    back = api.call(root, "calendar", "GET", _path(a, ev["id"]))
    print("%s event %r (%s) with %s; notified: %s (sendUpdates=%s)"
          % (verb, ev.get("summary"), ev["id"], seen(ev), notified(ev, a.notify), a.notify))
    print("READ BACK: the calendar shows %r, %s – %s, %s"
          % (back.get("summary"), (back.get("start") or {}).get("dateTime") or (back.get("start") or {}).get("date"),
             (back.get("end") or {}).get("dateTime") or (back.get("end") or {}).get("date"), seen(back)))
    return 0


def _body(root, a):
    body = {"guestsCanSeeOtherGuests": bool(a.guests_see_each_other)}
    for key, val in (("summary", a.title), ("description", a.description)):
        if val is not None:
            body[key] = val
    if a.start:
        body["start"] = _when(a.start, a.tz)
    if a.end:
        body["end"] = _when(a.end, a.tz)
    guests = _guests(root, a)
    if guests is not None:
        body["attendees"] = [{"email": g} for g in guests]
    return body


def create(root, a):
    if not (a.title and a.start and a.end):
        print("usage: calendar create needs --title, --start and --end")
        return 1
    body = _body(root, a)
    code, lines = gate(root, a, body)
    if code:
        print("\n".join(lines))
        return code
    ev = api.call(root, "calendar", "POST", _path(a), {"sendUpdates": a.notify}, body)
    return _report(root, a, "CREATED", ev)


def update(root, a):
    old = api.call(root, "calendar", "GET", _path(a, a.event))
    body = _body(root, a)
    code, lines = gate(root, a, dict(old, **body))
    if code:
        print("\n".join(lines))
        return code
    ev = api.call(root, "calendar", "PATCH", _path(a, a.event), {"sendUpdates": a.notify}, body)
    return _report(root, a, "UPDATED", ev)
