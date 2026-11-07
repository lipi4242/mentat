"""The words mentat_dates.py says back (hu/en): one label per reading, one sentence per answer."""

WD = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
      "hu": ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]}
L = {"en": {"given": "the given dates", "upto": "from today up to and including that day", "today": "today",
            "tomorrow": "tomorrow", "dayafter": "the day after tomorrow", "yesterday": "yesterday",
            "in": "{n} {u} from today, that one day", "from_today": "from today", "from_tomorrow": "from tomorrow",
            "weekend": "the coming weekend", "weekend_after": "the weekend after that",
            "coming": "the coming {wd}", "next_week_wd": "{wd} of next week", "this_week_wd": "{wd} of this week",
            "cal_week": "the calendar week", "seven": "the next 7 days", "past7": "the past 7 days",
            "rest": "from today to its end", "last_day": "the last day of the month",
            "last7": "the last 7 days of the month", "cal_month": "the calendar month",
            "thirty": "the next 30 days", "past30": "the past 30 days"},
     "hu": {"given": "a megadott dátumok", "upto": "mától eddig a napig, azt is beleértve", "today": "ma",
            "tomorrow": "holnap", "dayafter": "holnapután", "yesterday": "tegnap",
            "in": "mától számítva {n} {u}, az az egy nap", "from_today": "mától", "from_tomorrow": "holnaptól",
            "weekend": "a legközelebbi hétvége", "weekend_after": "az azutáni hétvége",
            "coming": "a legközelebbi {wd}", "next_week_wd": "a jövő heti {wd}", "this_week_wd": "az e heti {wd}",
            "cal_week": "a naptári hét", "seven": "a következő 7 nap", "past7": "az elmúlt 7 nap",
            "rest": "mától a végéig", "last_day": "a hónap utolsó napja",
            "last7": "a hónap utolsó 7 napja", "cal_month": "a naptári hónap",
            "thirty": "a következő 30 nap", "past30": "az elmúlt 30 nap"}}
SAY = {"en": {"exact": "“{p}” = {r} ({tz} time, both days included).",
              "confirm": "“{p}” can mean more than one thing: {r}. Ask the USER which one before using it "
                         "({tz} time, both days included).",
              "unknown": "I cannot turn “{p}” into dates reliably: ask the USER for the exact dates."},
       "hu": {"exact": "„{p}” = {r} ({tz} idő szerint, mindkét nap benne van).",
              "confirm": "„{p}” többféleképpen érthető: {r}. Előbb kérdezd meg a FELHASZNÁLÓT, melyikre gondol "
                         "({tz} idő szerint, mindkét nap benne van).",
              "unknown": "„{p}” nem alakítható biztosan dátummá: kérdezd meg a FELHASZNÁLÓTÓL a pontos dátumokat."}}


UNIT = {"en": {"day": "day(s)", "week": "week(s)", "month": "month(s)"}, "hu": {"day": "nap", "week": "hét", "month": "hónap"}}


def label(key, kv, lang):
    lang = lang if lang in L else "en"
    kv = dict(kv)
    if "u" in kv:
        kv["u"] = UNIT[lang][kv["u"]]
    if "wd" in kv:
        kv["wd"] = WD[lang][kv["wd"]]
    return L[lang][key].format(**kv)


def _span(c):
    return c["start"] if c["start"] == c["end"] else "%s – %s" % (c["start"], c["end"])


def say(phrase, status, cands, tz, lang):
    lang = lang if lang in SAY else "en"
    if status == "exact":
        r = "%s, %s" % (_span(cands[0]), cands[0]["label"])
    else:
        r = "; ".join("(%s) %s, %s" % ("abcdef"[i], _span(c), c["label"]) for i, c in enumerate(cands))
    return SAY[lang][status].format(p=phrase, r=r, tz=tz)
