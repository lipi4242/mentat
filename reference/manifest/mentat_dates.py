#!/usr/bin/env python3
"""mentat_dates.py — a relative time phrase to concrete dates, or the honest answer that it is ambiguous.

    python3 .mentat/bin/mentat_dates.py "jövő héten" --tz Europe/Budapest [--today YYYY-MM-DD]
                                        [--week-start mon|sun] [--lang hu|en] [--json]

exact (exit 0): one reading; the dates go into the contract's window as they are.
confirm (exit 3): more than one reading ("next week": the calendar week, or the next 7 days?);
    it lists them, and you ask the USER which one before using any. It never picks one.
unknown (exit 1): not understood (another language, an unusual phrase): ask for the dates.
Dates are calendar days in --tz, both ends included (00:00 on the first, 24:00 on the last).
Pass only the time phrase, not the whole request. English and Hungarian words: mentat_dates_words.py.
"""
import argparse
import calendar
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_dates_text as text  # noqa: E402
import mentat_dates_words as w  # noqa: E402

D = dt.timedelta


def _month_end(d, months=0):
    y, m = divmod(d.month - 1 + months, 12)
    return dt.date(d.year + y, m + 1, calendar.monthrange(d.year + y, m + 1)[1])


def _add(d, n, unit):
    if unit == "month":
        end = _month_end(d, n)
        return end.replace(day=min(d.day, end.day))
    return d + D(days=n * {"day": 1, "week": 7, "fortnight": 14}[unit])


def readings(cs, today, ws):
    """[(start, end, label key, label values)]; one = exact, several = confirm, none = unknown."""
    k = [c[0] for c in cs]
    has, val = set(k), {c[0]: c[1] for c in cs}
    if "?" in has or not cs:
        return []
    week0 = today - D(days=(today.weekday() - ws) % 7)
    if "date" in has:
        ds = sorted(dt.date.fromisoformat(v) for c, v in cs if c == "date")
        return [(ds[0], ds[-1], "given", {})]
    day = {"today": 0, "tomorrow": 1, "dayafter": 2, "yesterday": -1}
    if "after" in has:   # only "the day after tomorrow"; "after the weekend" is not a range we know
        if "tomorrow" not in has:
            return []
        has.add("dayafter")
    hit = next((x for x in ("dayafter", "today", "tomorrow", "yesterday") if x in has), None)
    if hit:
        d = today + D(days=day[hit])
        return [(today, d, "upto", {})] if "by" in has and d > today else [(d, d, hit, {})]
    unit = next((x for x in reversed(k) if x in w.UNITS), None)
    if unit and ("num" in has or unit == "fortnight") and has & {"in", "within", "next", "by"}:
        n = val.get("num", 1) * (2 if unit == "fortnight" else 1)
        unit = "week" if unit == "fortnight" else unit
        if "in" in has and not has & {"within", "by"}:
            d = _add(today, n, unit)
            return [(d, d, "in", {"n": n, "u": unit})]
        end = _add(today, n, unit)
        return [(today, end, "from_today", {}), (today + D(days=1), end, "from_tomorrow", {})]
    if "weekend" in has:
        wkd = today.weekday()
        sat = today + D(days=5 - wkd) if wkd < 5 else today - D(days=wkd - 5)
        this, after = (max(sat, today), sat + D(days=1), "weekend", {}), (sat + D(days=7), sat + D(days=8), "weekend_after", {})
        if "by" in has:
            return [(today, sat + D(days=1), "upto", {})]
        if "next" in has:
            return [this, after] if wkd < 5 else [after]
        return [this] if wkd < 5 else [this, after]
    if "wd" in has:
        wd = val["wd"]
        coming = today + D(days=(wd - today.weekday() - 1) % 7 + 1)
        in_week = week0 + D(days=(wd - ws) % 7)
        if "by" in has:
            return [(today, coming if coming > today else today, "upto", {})]
        nearest, alt = (coming, coming, "coming", {"wd": wd}), in_week + D(days=7)
        if "next" in has:
            return [nearest] + ([] if alt == coming else [(alt, alt, "next_week_wd", {"wd": wd})])
        this = (in_week, in_week, "this_week_wd", {"wd": wd})
        if "this" in has:
            return [this] if in_week >= today else [this, nearest]
        return [(today, today, "today", {}), nearest] if today.weekday() == wd else [nearest]
    if "week" in has:
        if "end" in has:   # "by the end of the week" is a range; "end of next week" is not one day we know
            return [(today, week0 + D(days=6), "upto", {})] if "by" in has and not has & {"next", "last"} else []
        if "next" in has:
            return [(week0 + D(days=7), week0 + D(days=13), "cal_week", {}), (today + D(days=1), today + D(days=7), "seven", {})]
        if "last" in has:
            return [(week0 - D(days=7), week0 - D(days=1), "cal_week", {}), (today - D(days=7), today - D(days=1), "past7", {})]
        return [(week0, week0 + D(days=6), "cal_week", {})] + ([] if week0 == today else [(today, week0 + D(days=6), "rest", {})])
    if "month" in has:
        shift = 1 if "next" in has else -1 if "last" in has else 0
        last = _month_end(today, shift)
        first = last.replace(day=1)
        if "end" in has:
            return [(today, last, "upto", {})] if "by" in has else [(last, last, "last_day", {}), (last - D(days=6), last, "last7", {})]
        if shift == 1:
            return [(first, last, "cal_month", {}), (today + D(days=1), today + D(days=30), "thirty", {})]
        if shift == -1:
            return [(first, last, "cal_month", {}), (today - D(days=30), today - D(days=1), "past30", {})]
        return [(first, last, "cal_month", {})] + ([] if today.day == 1 else [(today, last, "rest", {})])
    return []


def resolve(phrase, tz, today, week_start="mon", lang="en"):
    ws = 0 if week_start == "mon" else 6
    found = readings(w.concepts(phrase), today, ws)
    status = "unknown" if not found else "exact" if len(found) == 1 else "confirm"
    cands = [{"start": a.isoformat(), "end": b.isoformat(), "label": text.label(key, kv, lang)}
             for a, b, key, kv in found]
    return {"input": phrase, "today": today.isoformat(), "tz": tz, "status": status, "candidates": cands,
            "boundary": "calendar days in %s, both ends included" % tz, "say": text.say(phrase, status, cands, tz, lang)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_dates.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("phrase")
    p.add_argument("--tz", required=True)
    p.add_argument("--today", help="YYYY-MM-DD (default: today in --tz)")
    p.add_argument("--week-start", choices=["mon", "sun"], default="mon")
    p.add_argument("--lang", choices=["hu", "en"], default="en")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo(a.tz))
    except (KeyError, ValueError, ImportError) as e:
        p.error("unknown --tz %r (%s)" % (a.tz, e))
    today = dt.date.fromisoformat(a.today) if a.today else now.date()
    r = resolve(a.phrase, a.tz, today, a.week_start, a.lang)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else r["say"])
    return {"exact": 0, "confirm": 3, "unknown": 1}[r["status"]]


if __name__ == "__main__":
    sys.exit(main())
