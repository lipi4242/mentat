"""`fleet probe <ágens|ssh-cél>` — elérhetőségi és auth-szonda bármely gépről.

Az ágens-összeolvasztás 0. lépése (2026-10-29): mindkét érintett ágens napok óta
„Login expired"-ben állt, a modellt a unitból olvastuk (a transzkript mást mondhat), és az
egyik box fleet-checkoutja meg registry-forrása hetek óta nem frissült — ezért nem volt
rajta auth-riasztás sem. Ezt egy hívás mondja meg, a box saját szemével (agent_probe.py
a box python3-jának stdin-jén; a régi fleet-kód nem számít).
"""
from __future__ import annotations
import json
import shlex
from pathlib import Path

from fleet import outward_hold
from fleet.remote import Target, resolve

PROBE = Path(__file__).with_name("agent_probe.py")


def run_probe(name: str, *, ssh: str | None = None, account: str | None = None, fetch: bool = True,
              resolver=resolve) -> dict:
    entry, tgt = resolver(name, ssh=ssh)
    if entry is None and not ssh:
        raise SystemExit(f"{name}: nincs a registryben — add meg a boxot: `fleet probe {name} --ssh <user@box>`")
    agent = entry["agent"] if entry else name
    spec = {"agent": agent, "account": account or (entry or {}).get("claude_account") or "shared",
            "fetch": fetch}
    r = tgt.sh("python3 - " + shlex.quote(json.dumps(spec)), stdin=PROBE.read_text(), timeout=180)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else None
    except (ValueError, IndexError):
        out = None
    if out is None:
        return {"agent": agent, "target": tgt.label, "reachable": False,
                "errors": [f"a szonda nem futott (kód {r.returncode}): {(r.stderr or '').strip()[-300:]}"],
                "problems": ["elérhetetlen — ssh/python3 a boxon?"]}
    out.update(target=tgt.label, reachable=True, expected_model=(entry or {}).get("model"))
    wd = (entry or {}).get("workdir")
    out["outward_hold"] = outward_hold.show(tgt, wd) if wd else {"error": "nincs workdir (registry nélkül)"}
    out["problems"] = problems(out)
    return out


def problems(p: dict) -> list[str]:
    """Pure: ami miatt merge/upgrade előtt meg kell állni. Az ismeretlen is probléma."""
    out = []
    if p.get("auth") == "expired":
        out.append(f"login lejárt {p.get('auth_since')} óta ({p.get('failed')} üzenet kapott hibát) "
                   f"— `fleet login {p['agent']}`")
    elif p.get("auth") is None:
        out.append("auth ismeretlen: nincs assistant-válasz a transzkriptben")
    for key, what in (("fleet", "fleet-checkout"), ("registry", "registry-forrás")):
        g = p.get(key) if key == "fleet" else (p.get("registry") or {}).get("git")
        if not g:
            out.append(f"{what}: nem mérhető")
        elif g.get("behind") is None:
            out.append(f"{what}: nincs upstream / nem mérhető, hány committal van mögötte")
        elif g["behind"] > 0:
            out.append(f"{what} {g['behind']} committal az origin mögött ({g['path']}) — `git -C {g['path']} pull`")
        if g and not g.get("fetched"):
            out.append(f"{what}: a fetch nem futott le — a „mögötte” szám a legutóbbi fetch óta értendő")
    return out


def format_probe(p: dict) -> str:
    if not p.get("reachable"):
        return f"{p['agent']} @ {p['target']}: ELÉRHETETLEN\n  " + "\n  ".join(p["errors"])
    fl, rg = p.get("fleet") or {}, p.get("registry") or {}
    lines = [f"{p['agent']} @ {p['target']}  (fiók: {p['account']}, box TZ: {p.get('timezone') or '?'})",
             f"  auth:     {p.get('auth') or 'ismeretlen'}" + (f" — utolsó valódi válasz {p['last_ok_at']}"
                                                              if p.get("last_ok_at") else ""),
             f"  modell:   {p.get('model') or '?'} (transzkript, {p.get('model_at') or '-'})"
             + (f"; registry: {p['expected_model']}" if p.get("expected_model") else ""),
             f"  fleet:    {fl.get('version') or '?'} {fl.get('branch') or '?'}@{fl.get('head') or '?'}"
             f" ({fl.get('path') or '?'}) mögötte: {fl.get('behind', '?')}",
             f"  registry: {rg.get('path') or '?'} → {rg.get('realpath') or '?'} ({rg.get('source')})"
             f" mögötte: {(rg.get('git') or {}).get('behind', '?')}"]
    if "outward_hold" in p:
        lines.append("  " + outward_hold.line(p["outward_hold"]))
    lines += [f"  ! {x}" for x in p.get("problems", [])] or ["  minden jel rendben"]
    lines += [f"  (mérési hiba) {x}" for x in p.get("errors", [])]
    return "\n".join(lines)


def cmd_probe(a) -> int:
    rows = [run_probe(n, ssh=a.ssh, account=a.account, fetch=not a.no_fetch) for n in a.agents]
    print(json.dumps(rows, ensure_ascii=False, indent=2) if a.json else "\n\n".join(map(format_probe, rows)))
    return 0 if all(not r["problems"] for r in rows) else 1


def add_parser(sub) -> None:
    x = sub.add_parser("probe", help="elérhetőség + auth + valódi modell + box-checkout/registry lemaradás, "
                                     "bármely gépről (ssh)")
    x.add_argument("agents", nargs="+", metavar="ágens")
    x.add_argument("--ssh", metavar="user@box", help="a box, ha az ágens nincs (ezen a gépen) a registryben, "
                                                    "vagy a registry régi")
    x.add_argument("--account", help="Claude-fiók, ha az ágens nincs a registryben (alap: shared)")
    x.add_argument("--no-fetch", action="store_true", help="ne fetch-eljen (a lemaradás a legutóbbi fetch óta)")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=cmd_probe)
