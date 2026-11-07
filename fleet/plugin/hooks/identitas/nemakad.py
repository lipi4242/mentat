#!/usr/bin/env python3
"""Nem-akadó jóváhagyás: felügyelet nélkül egyetlen engedélykérés se várjon örökké.

    nemakad.py --hook          PermissionRequest hook: JSON a stdin-en; felügyelet nélkül deny + javaslat
    nemakad.py alszom [ÓÓ:PP]  felügyelet nélküli mód a következő ÓÓ:PP-ig (alap: 08:00)
    nemakad.py ebren           vissza a kérdező módba
    nemakad.py allapot         melyik mód él, és miért
    nemakad.py naplo [óra]     az utolsó N óra (alap 24) megtagadásai, a reggeli jelentéshez

A hook CSAK két dolgot tehet: semmit (a Claude Code a szokásos módon kérdez, mert van ember),
vagy deny (nincs ember). Allow-t SOHA nem ad: így a legrosszabb eset egy kihagyott lépés,
nem egy jóvá nem hagyott parancs.

Felügyelet nélküli, ha: `MENTAT_HEADLESS` (ugyanaz a jel, mint az identitás-kapué), vagy
`FLEET_AGENT`/`THUFIR_AGENT` (a box-unit indítója exportálja), vagy a hívás cwd-jében
`.claude/fleet.json` (flotta-ágens repója, mint a kapu headless-jelénél), vagy él a
`~/.mentat/felugyelet-nelkul` jelzőfájl (első sora: lejárat, epoch-másodperc). Lejárt vagy
hiányzó jelző: kérdező mód. Olvashatatlan vagy értelmezhetetlen jelző: felügyelet nélküli,
mert valaki szándékosan létrehozta, és a deny semmit nem enged át.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemakad_alak as alak  # noqa: E402
import nemakad_allapot as allapot  # noqa: E402

MAX_STDIN = 1 << 20


def deny(msg):
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                   "decision": {"behavior": "deny", "message": msg, "interrupt": False}}}


def hook(raw, now=None):
    """A stdin szövegéből a kiírandó dict, vagy None (kérdező mód: nem szólunk bele)."""
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        data = None
    if not isinstance(data, dict):
        data = {}
    try:
        felugy_nelkul = allapot.mod(now, data.get("cwd"))[0]
    except Exception:  # noqa: BLE001 - ha a mód sem dönthető el, ne akadjon meg
        felugy_nelkul = True
    if not felugy_nelkul:
        return None
    tool = data.get("tool_name") if isinstance(data.get("tool_name"), str) else "?"
    try:
        shape = alak.shape(tool, data.get("tool_input"))
        msg = alak.message(tool, data.get("tool_input"))
    except Exception:  # noqa: BLE001
        shape, msg = "hiba", alak.GENERIC
    allapot.naploz(data, tool, shape)
    return deny(msg)


def main(argv):
    if argv[:1] == ["--hook"]:
        out = hook(sys.stdin.buffer.read(MAX_STDIN).decode("utf-8", "replace"))
        if out:
            print(json.dumps(out, ensure_ascii=False))
        return 0
    if argv[:1] == ["alszom"]:
        print("felügyelet nélkül eddig:", allapot.alszom(*argv[1:2]).strftime("%Y-%m-%d %H:%M"))
        return 0
    if argv[:1] == ["ebren"]:
        if os.path.exists(allapot.jelzo()):
            os.remove(allapot.jelzo())
        print("kérdező mód")
        return 0
    if argv[:1] == ["allapot"]:
        f, ok = allapot.mod()
        print("felügyelet nélkül" if f else "kérdező mód", "|", ok)
        return 0
    if argv[:1] == ["naplo"]:
        print("\n".join(allapot.naplo(float(argv[1]) if len(argv) > 1 else 24.0)) or "nincs megtagadás")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
