"""`fleet retire <ágens>` — egy ágens VISSZAVONHATÓ nyugdíjazása a saját boxán.

2026-10-29 (ágens-összeolvasztás): a donor-ágenst előbb állítjuk le, és csak később
töröljük. Ha a login meggyógyul, a halott ágens is feléledne, és a cronjai a fogadó
ágenssel párhuzamosan írnának kifelé (issue-tracker, csoport). A végleges állapot — a
registryben `dormant` — emberi jóváhagyású PR a registry repójában; ez a parancs azt
NEM írja, csak kinyomtatja a teendőket.

  zár (alapból 30 nap) → unit stop + disable (reboot után se induljon) → híd stop + disable
  → ami még élhet: az ágens nevét/workdirjét említő user-timerek és crontab-sorok, a box TZ-je
"""
from __future__ import annotations
import time

from fleet import agentctl
from fleet.txn import run_cmd

DEFAULT_TTL_MIN = 30 * 24 * 60


def leftovers(entry: dict, run=run_cmd) -> list[str]:
    """Pure-ish: user-timerek és crontab-sorok, amik az ágensre utalnak (csak olvas)."""
    keys = {entry["agent"], entry.get("session") or entry["agent"]}
    wd = (entry.get("workdir") or "").replace("%h/", "")
    if wd:
        keys.add(wd)
    out = []
    t = run(["systemctl", "--user", "list-timers", "--all", "--no-legend"])
    for ln in (t.stdout or "").splitlines() if t.returncode == 0 else []:
        if any(k in ln for k in keys):
            out.append("timer: " + " ".join(ln.split()))
    c = run(["crontab", "-l"])
    for ln in (c.stdout or "").splitlines() if c.returncode == 0 else []:
        if ln.strip() and not ln.lstrip().startswith("#") and any(k in ln for k in keys):
            out.append("cron: " + ln.strip())
    return out


def box_tz(run=run_cmd) -> str:
    r = run(["timedatectl", "show", "-p", "Timezone", "--value"])
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "ismeretlen"


def retire(entry: dict, *, ttl_min: int = DEFAULT_TTL_MIN, run=run_cmd, now: float | None = None) -> dict:
    a, unit = entry["agent"], entry["unit"]
    bridge = (entry.get("bridge") or {}).get("unit")
    r = agentctl.stop(entry, hold_min=ttl_min, run=run)
    notes = list(r["notes"])
    if not r["ok"]:
        return {"ok": False, "notes": notes}
    for verb, u in [("disable", unit)] + ([("stop", bridge), ("disable", bridge)] if bridge else []):
        x = run(["systemctl", "--user", verb, u])
        notes.append(f"{verb} {u}: " + ("ok" if x.returncode == 0 else f"kód {x.returncode} {x.stderr.strip()}"))
    until = time.strftime("%Y-%m-%d %H:%M", time.localtime((now or time.time()) + ttl_min * 60))
    left = leftovers(entry, run)
    notes += [f"a zár {until}-ig él; addig a registry-PR-nek be kell érnie, különben a reconcile visszaindítja"]
    notes += ["", "visszavonás: `systemctl --user enable " + unit + (f" {bridge}" if bridge else "")
              + f"` és `fleet restart {a}`" + (f", majd `systemctl --user start {bridge}`" if bridge else "")]
    return {"ok": True, "notes": notes, "leftovers": left, "tz": box_tz(run),
            "checklist": checklist(entry, left, until)}


def checklist(entry: dict, left: list[str], until: str) -> list[str]:
    a = entry["agent"]
    return [
        f"[ ] registry-PR (emberi sáv, a registry repójában): agents.json → {a}: \"status\": \"dormant\" "
        f"— {until} előtt",
        "[ ] a merge után MINDEN boxon, amelynek a registry-mutatója erre a repóra mutat: git pull "
        f"(ellenőrzés: `fleet probe {a}` → registry mögötte: 0)",
        *(f"[ ] még él: {x} — a fogadó ágenshez költözik vagy leáll (a box TZ-jében számolva!)" for x in left),
        "[ ] a donor nem merge-elt ágai és élő checkoutja átnézve (a döntések ott is élhetnek)",
        "[ ] a donor kifelé menő kulcsai (issue-tracker, naptár, connect-token): a fogadó saját kulcsot kap "
        "a SAJÁT boxán; a donoré visszavonva, miután a fogadó első éles feladata zöld",
        "[ ] Telegram-bot: a donoré leállítva marad; a csoportokból kivenni vagy átadni — a tulajdonos dönt",
    ]


def cmd_retire(a) -> int:
    from fleet.cli import _entry_or_die
    r = retire(_entry_or_die(a.agent), ttl_min=a.ttl)
    print("\n".join(r["notes"]))
    if r["ok"]:
        print(f"\nbox TZ: {r['tz']}")
        print("\nteendők a végleges nyugdíjazáshoz:\n" + "\n".join(r["checklist"]))
    return 0 if r["ok"] else 1


def add_parser(sub) -> None:
    x = sub.add_parser("retire", help="visszavonható nyugdíjazás: hosszú zár + unit és híd stop/disable "
                                      "+ a registry-dormant PR teendői (a registryt nem írja)")
    x.add_argument("agent")
    x.add_argument("--ttl", type=int, default=DEFAULT_TTL_MIN, metavar="PERC", help="a zár hossza (alap: 30 nap)")
    x.set_defaults(fn=cmd_retire)

