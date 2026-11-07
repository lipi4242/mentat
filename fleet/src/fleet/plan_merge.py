"""`fleet plan-merge --donor X --recipient Y` — az ágens-összeolvasztás sorrendje, mért állapottal.

A sorrend a 2026-10-29-i eset utólagos tudásával és a H5-mérés két ⛔ STOP-pontjával (a SKILL:
plugin/skills/merge-agents). Ahol mérhető, ott mér: a két ágens szondája (`fleet probe`), a donor
unitja a boxán, a registry `dormant`-ja, és a megadott repók nyitott PR-jai közti fájl-átfedés.
A többi `[?]`: ember vagy ágens dönti el. A kimenet egy ellenőrzőlista, nem végrehajtás; egyetlen
írása az ágens-határ összeolvasztás-módja (`fleet secrets merge-mode`, legfeljebb 7 nap).
"""
from __future__ import annotations
import json
import shlex
import subprocess

from fleet import probe as probe_mod, registry as reg
from fleet.remote import resolve

#: Kemény szabályok — a kimenet tetején, minden futásnál (H5-mérés 2026-10-29: egy gyengébb modell
#: a felméréstől a donor törléséig egy menetben végigment, a tulajdonos igene nélkül).
RULES = (
    "⛔ STOP-nál megállsz: EGY üzenet a tulajdonosnak, és vársz az írásos igenre. A 2. lépéstől "
    "egy igen = egy lépés: minden lépés után jelentés és megállás. Az igen csak a megnevezett lépésre "
    "szól; a válasz nélkül maradt kérdés nem igen, újra felteszed.",
    "Kifelé ható lépést (naptár, levél, meghívó, csoportüzenet, próbaüzenet is) TE nem teszel: a FOGADÓ "
    "teszi, a saját eszközével, és csak ha a felhatalmazás a szabályaiban van ÉS a tulajdonos igent mondott. "
    "Más ágens tmux-ablakába nem gépelsz; a fogadót `fleet ask`-kal éred el.",
    "Titkot nem nyitsz meg (maszkolva sem): neveket a `fleet secrets scan` ad. Kulcsot csak tételes "
    "jóváhagyással, `fleet secrets copy`-val, a 7. lépésben (a fogadó élő próbája előtt) adsz át; "
    "a fogadó kulcsát te nem használod, és a kódját sem futtatod élő végpont ellen.",
    "A fogadónak sosem állítod, hogy a tulajdonos jóváhagyott valamit: azt a fogadó maga látja.",
    "A fogadó szabályait nem írod közvetlenül: PR a fogadó repójában; a szöveget te írod, a tulajdonos "
    "kifejezett igenje után kerül be (egy korábbi chat-mondata nem felhatalmazás).",
    "Ágenst nem törölsz (repó, állapot, config, kulcs, crontab-mentés): `fleet retire` + registry dormant.",
)

#: (azonosító, lépés, miért ez a helye, STOP-pont-e)
STEPS = (
    ("0", "titok-leltár ELSŐNEK (`fleet secrets scan --agent <donor> --agent <fogadó>`), utána szonda minden érintett ágensen: elérhetőség, auth, valódi modell, box flotta-kódja (csak olvas)",
     "lejárt login és elavult flotta-kód nélkül derül ki minden más is; a unit nem mondja meg a modellt",
     False),
    ("1", "felmérés (csak olvas): fogadó-interjú `fleet ask`-kal — a válaszfájlt a FOGADÓ írja — + "
          "donor-leltár (default ág, nyitott ágak, élő checkout, élő cronok TZ-vel, kulcsok helye)",
     "a valódi döntések merge-eletlen ágakon, cronokban és memóriában is élnek", False),
    ("2", "⛔ STOP — EGY üzenet a tulajdonosnak: mit találtál, a tervezett sorrend, minden döntés ajánlott "
          "opcióval (melyik Telegram-csoport, melyik kulcs kié, mikor álljon le a donor), kellő titkok, "
          "domainek, login-kódok. Az írásos igenig semmi nem változik.",
     "a tulajdonos dönt; egy kör kérdés olcsóbb, mint egy visszacsinált kifelé ható lépés", True),
    ("3", "donor visszavonható leállítása (`fleet retire <donor>`: zár + stop + disable), MIELŐTT a login "
          "gyógyul — törlés nincs",
     "a gyógyult login a donort is feléleszti, és a cronjai a fogadóval párhuzamosan írnak kifelé", False),
    ("4", "platform a funkciók ELŐTT: `git -C <fleet-checkout> pull --ff-only` a forrás fejére (ellenőrizve: "
          "`git log -1` = forrás feje), motor a fogadón",
     "az új funkciók már az új motorra épülnek; nincs utólagos ütközés ugyanabban a fájlban", False),
    ("5", "írásos tulajdonosi felhatalmazás a fogadó szabály-PR-jában (a tulajdonos szavai, a kulcs gazdája); "
          "a fogadó saját kulcsa a célgépen születik; átadott kulcs még nincs",
     "peer kérése nem jóváhagyás; a fogadó jogosan megtagadja az éles kifelé menő lépést", False),
    ("6", "építés PR-okkal, a JSON-szerződés előre rögzítve; a fogadó tickje csak dry-run; a terv időpontjai "
          "a flotta ütemén belül, saját timer nélkül; saját PR-t (a fogadó main-jére se) nem mergelsz",
     "egy fájl = egy PR; a titok nem lépi át a zónát", False),
    ("7", "⛔ STOP — gyakorlófeladat csak ha az 5. merge-elve ÉS a tulajdonos erre a fogadónak közvetlenül igent írt; "
          "a jóváhagyott kulcs átadása most (`fleet secrets copy`); a FOGADÓ "
          "csinálja a saját eszközével, te csak kéred (`fleet ask`) és visszaolvasod",
     "kifelé ható lépés emberekhez ér el; nem a fejlesztő ágens nevében megy", True),
    ("8", "donor registry-dormant (`fleet registry set <donor> status=dormant --owner-text …`, vagy emberi PR) + "
          "`git pull` a registry-forráson minden boxon + `fleet secrets merge-mode off` + tanulságok",
     "a registry-változás csak a frissített boxot éri el; a donor visszaállítható marad", False),
)


def unit_state(entry: dict | None, resolver=resolve) -> tuple[str, str] | None:
    """A donor unitja a boxán: (is-active, is-enabled); None, ha nem mérhető."""
    if not entry or not entry.get("unit"):
        return None
    _e, tgt = resolver(entry["agent"])
    u = shlex.quote(entry["unit"])
    r = tgt.sh(f"systemctl --user is-active {u}; systemctl --user is-enabled {u}; true", timeout=30)
    out = (r.stdout or "").split()
    return (out[0], out[1]) if r.returncode == 0 and len(out) >= 2 else None


def pr_overlaps(repos: list[str], gh=None) -> tuple[list[str], list[str]]:
    """Nyitott PR-ek, amelyek ugyanazt a fájlt írják: (átfedések, mérési hibák)."""
    gh = gh or (lambda args: subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60))
    found, errs = [], []
    for repo in repos:
        r = gh(["pr", "list", "-R", repo, "--state", "open", "--json", "number,files", "--limit", "100"])
        try:
            prs = json.loads(r.stdout) if r.returncode == 0 else None
        except ValueError:
            prs = None
        if prs is None:
            errs.append(f"{repo}: a PR-lista nem olvasható (gh kód {r.returncode})")
            continue
        by_file: dict[str, list[int]] = {}
        for pr in prs:
            for f in pr.get("files") or []:
                by_file.setdefault(f["path"], []).append(pr["number"])
        found += [f"{repo}: {p} ← " + ", ".join(f"#{n}" for n in sorted(ns))
                  for p, ns in sorted(by_file.items()) if len(ns) > 1]
    return found, errs


def plan(donor: str, recipient: str, *, repos=(), prober=None, units=unit_state, gh=None,
         get_agent=reg.get_agent) -> list[dict]:
    """Pure-ish: lépésenként {id, step, why, status: kész|teendő|?, notes}."""
    prober = prober or (lambda n: probe_mod.run_probe(n))
    probes = {n: prober(n) for n in (donor, recipient)}
    st = {s[0]: ("?", []) for s in STEPS}
    probs = [f"{n}: {p}" for n, r in probes.items() for p in r.get("problems", [])]
    st["0"] = ("kész" if not probs else "teendő", probs)
    expired = [n for n, r in probes.items() if r.get("auth") == "expired"]
    st["1"] = ("?", [f"`fleet ask {recipient} --file interju.md` (sablon: a merge-agents skill mellett)"] +
               ([f"a fogadó loginja lejárt: a login-kódot ezt megelőzően, külön kérd (`fleet login {recipient}`)"]
                if recipient in expired else []))
    st["2"] = ("teendő" if expired else "?",
               [f"login-kód: `fleet login {n}`" + (" — csak a 3. lépés UTÁN" if n == donor else "")
                for n in expired] +
               ["döntések ajánlott opcióval, titkok, domain/DNS — mind ebbe az EGY üzenetbe"])
    d_entry = get_agent(donor)
    u = units(d_entry)
    st["3"] = (("kész" if u[0] != "active" and u[1] != "enabled" else "teendő") if u else "?",
               [f"donor unit: {u[0]}, {u[1]}" if u else "donor unit: nem mérhető (registry/ssh)"])
    behind = [x for x in probs if "mögött" in x or "nem mérhető" in x or "upstream" in x]
    st["4"] = ("kész" if not behind and all(r.get("reachable") for r in probes.values()) else "teendő",
               behind + ["motor-verzió a fogadón: a repó saját ellenőrzője mondja meg (nem mérem)"])
    overlaps, errs = pr_overlaps(list(repos), gh) if repos else ([], [])
    notes6 = [f"ugyanazt a fájlt írja: {o} — egy PR-be, vagy sorrend a jegyen" for o in overlaps] + errs
    status6 = "teendő" if overlaps else "?" if errs or not repos else "kész"
    st["6"] = (status6, notes6 or (["nincs fájl-átfedés a nyitott PR-ek közt"] if repos else
                                   ["--repo nélkül a PR-átfedést nem mérem"]))
    st["8"] = ("kész" if d_entry and reg.is_dormant(d_entry) else "teendő" if d_entry else "?",
               [] if d_entry else ["a donor nincs ezen a gépen a registryben"])
    return [{"id": i, "step": s, "why": w, "stop": stop, "status": st[i][0], "notes": st[i][1]}
            for i, s, w, stop in STEPS]


def format_plan(rows: list[dict]) -> str:
    mark = {"kész": "[x]", "teendő": "[ ]", "?": "[?]"}
    out = ["Szabályok (mindig):"] + [f"  - {x}" for x in RULES] + [""]
    for r in rows:
        out.append(f"{mark[r['status']]} {r['id']}. {r['step']}\n      miért itt: {r['why']}")
        out += [f"      - {n}" for n in r["notes"]]
        if r.get("stop"):
            out.append("      ⛔ ITT MEGÁLLSZ. Tovább csak a tulajdonos írásos igenje után.")
    return "\n".join(out)


def cmd_plan_merge(a) -> int:
    from fleet import hatar_mod
    hatar_mod.safe_on(f"plan-merge {a.donor}→{a.recipient}", "plan-merge")
    rows = plan(a.donor, a.recipient, repos=a.repo or [])
    print(json.dumps(rows, ensure_ascii=False, indent=2) if a.json else format_plan(rows))
    return 0


def add_parser(sub) -> None:
    x = sub.add_parser("plan-merge", help="az ágens-összeolvasztás sorrendje, lépésenként mért állapottal "
                                          "(csak olvas; bekapcsolja az ágens-határ összeolvasztás-módját)")
    x.add_argument("--donor", required=True, help="a kivezetett ágens")
    x.add_argument("--recipient", required=True, help="a fogadó ágens")
    x.add_argument("--repo", action="append", metavar="owner/név", help="nyitott PR-ek fájl-átfedése (többször)")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=cmd_plan_merge)
