"""`fleet` — a box-oldali parancssor. Vékony: minden döntés a modulokban él,
itt csak argumentum-feldolgozás és kiírás van.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from fleet import __version__, registry_dir, RegistryNotConfigured, PLUGIN_DIR
from fleet import registry as reg


def _print(obj) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(obj)


def _entry_or_die(name: str) -> dict:
    e = reg.get_agent(name)
    if e is None:
        print(f"nincs ilyen ágens a registryben: {name}", file=sys.stderr)
        raise SystemExit(2)
    return e


# ── parancsok ──────────────────────────────────────────────────────────

def cmd_validate(_a) -> int:
    from fleet.validate import validate
    rdir = registry_dir()
    n, problems = validate(rdir)
    for p in problems:
        print(p)
    print(f"validate: {rdir}: {n} ágens, {len(problems)} probléma")
    return 1 if problems else 0


def cmd_render(a) -> int:
    from fleet.install import unit_text_for
    print(unit_text_for(_entry_or_die(a.agent)), end="")
    return 0


def cmd_install(a) -> int:
    from fleet.install_flow import install_agent, format_install
    r = install_agent(_entry_or_die(a.agent))
    _print(r) if a.json else print(format_install(r))
    return {"ok": 0, "pending": 3}.get(r["status"], 1)


def cmd_preflight(a) -> int:
    from fleet.preflight import preflight
    # preflight() returns a LIST of findings (see preflight.py:313), not a dict.
    # Treating it as a dict raised AttributeError on EVERY run — including the
    # clean case, so "no findings" looked identical to "the tool is broken".
    from fleet.install_checks import tmux_problem
    from fleet.registry import is_dormant
    e = _entry_or_die(a.agent)
    findings = preflight(e) + ([] if is_dormant(e) else tmux_problem())
    _print(findings)
    return 0 if not findings else 1


def cmd_bridge_install(a) -> int:
    from fleet.bridge import install_bridge
    _print(install_bridge(_entry_or_die(a.agent)))
    return 0


def cmd_bridge_rollback(a) -> int:
    from fleet.bridge import rollback_bridge
    try:
        r = rollback_bridge(_entry_or_die(a.agent))
    except RuntimeError as e:
        print(f"hiba: {e}")
        return 1
    _print(r)
    if r["start_rc"] != 0:
        print(f"FIGYELEM: a {r['unit']} start nem sikerult (rc={r['start_rc']}) — a hid NEM fut!")
        return 1
    return 0


def cmd_bridge_status(_a) -> int:
    from fleet.bridge import bridge_status
    host = reg.local_host()
    for r in bridge_status(reg.agents_for_host(host)):
        flag = "DRIFT" if r["drift"] else "ok"
        print(f"{r['agent']:24} telepítve={r['installed'] or '-':8} repó={r['current']:8} {flag}")
        if r["changed"]:
            more = " ..." if len(r["changed"]) > 5 else ""
            print(f"  eltér: {', '.join(r['changed'][:5])}{more}")
    return 0


def cmd_lock(a) -> int:
    from fleet import maintenance
    p = maintenance.lock(a.agent, a.ttl)
    print(f"zár: {p} ({a.ttl} perc)")
    return 0


def cmd_unlock(a) -> int:
    from fleet import maintenance
    maintenance.unlock(a.agent)
    print(f"zár feloldva: {a.agent}")
    return 0


def cmd_unquarantine(a) -> int:
    from fleet.reconcile import load_state, save_state
    st = load_state(a.agent)
    st["quarantined"] = False
    st["failed_postchecks"] = 0
    save_state(a.agent, st)
    print(f"karantén feloldva: {a.agent}")
    return 0


def cmd_roster(a) -> int:
    from fleet.roster import roster, format_roster
    rows = roster(host=a.host or reg.local_host(), probe=not a.no_probe)
    print(json.dumps(rows, ensure_ascii=False, indent=2) if a.json else format_roster(rows))
    return 0


def cmd_doctor(a) -> int:
    from fleet.doctor import doctor, format_report
    reports = doctor(agent=a.agent, fix=a.fix)
    if a.json:
        _print(reports)
    else:
        print(format_report(reports))
    return 0 if all(r["ok"] for r in reports) else 1


def cmd_postcheck(a) -> int:
    from fleet.postcheck import postcheck, format_postcheck
    r = postcheck(_entry_or_die(a.agent), wait_s=a.wait)
    print(format_postcheck(r))
    return 0 if r["ok"] else 1


def cmd_reconcile(a) -> int:
    from fleet.reconcile import reconcile
    rep = reconcile(observe=a.observe, only=a.agent, fast=a.fast)
    for line in rep["lines"]:
        print(line)
    return 0


def cmd_join(a) -> int:
    from fleet.join import join
    _print(join(Path(a.repo).resolve(), agent=a.agent, brain=a.brain, reducer=a.reducer,
                fix_claude_md=a.fix_claude_md))
    return 0


def cmd_upgrade(a) -> int:
    from fleet.join import upgrade
    r = upgrade(Path(a.repo).resolve())
    _print(r)
    if r.get("plugin_migration"):
        print(f"fleet: a PR merge-e ELŐTT futtasd a boxon: {r['plugin_migration']['run_on_box_before_merge']}",
              file=sys.stderr)
    return 0 if r["ok"] else 1


def cmd_status(a) -> int:
    from fleet.status import status, format_status
    r = status(a.agent, repo=Path(a.repo).resolve() if a.repo else None)
    _print(r) if a.json else print(format_status(r))
    return 0


def cmd_release(a) -> int:
    from fleet.release import record_release, read_release
    if a.show:
        _print(read_release())
        return 0
    _print(record_release())
    return 0


def cmd_setup(a) -> int:
    from fleet.setup import setup, format_setup
    r = setup(a.agent, check=a.check, first_tick=not a.no_tick, fix_claude_md=a.fix_claude_md,
              plugin_source=a.plugin_source)
    _print(r) if a.json else print(format_setup(r))
    return {"ok": 0, "pending": 3}.get(r["status"], 1)


def cmd_init(a) -> int:
    from fleet.init import init
    r = init(a.agent, repo=Path(a.repo), model=a.model)
    print(r["summary"])
    return 0 if r["status"] == "ok" else 1


def cmd_wait_up(a) -> int:
    from fleet.agentctl import wait_up
    r = wait_up(_entry_or_die(a.agent), timeout_s=a.timeout)
    print("\n".join(r["notes"]))
    return 0 if r["ok"] else 1


def cmd_auth(a) -> int:
    import os
    from fleet.claude_auth import TOKEN_VAR, store_token, logged_in
    from fleet.install_checks import CLAUDE_BIN
    e = _entry_or_die(a.agent)
    from fleet.claude_auth import systemd_token
    tok = os.environ.get(TOKEN_VAR) or (systemd_token() if a.from_systemd else None) \
        or ("" if sys.stdin.isatty() else sys.stdin.readline().strip())
    if not tok:
        print(f"nincs {TOKEN_VAR} ebben a shellben, és a stdin üres. Futtasd abban a shellben, ahol a "
              f"claude be van jelentkezve, vagy: `claude setup-token`, majd `{TOKEN_VAR}=… fleet auth {a.agent}`",
              file=sys.stderr)
        return 1
    p = store_token(e, tok, Path.home())
    ok = logged_in(e, claude_bin=CLAUDE_BIN, home=Path.home())
    print(f"auth: a token a unitnak átadva: {p} (0600) — a unit szemével: "
          + ("bejelentkezve" if ok else "NEM érvényes (lejárt? `claude setup-token`)"))
    return 0 if ok else 1


def cmd_stop(a) -> int:
    from fleet.agentctl import stop
    r = stop(_entry_or_die(a.agent), hold_min=a.hold)
    print("\n".join(r["notes"]))
    return 0 if r["ok"] else 1


def cmd_restart(a) -> int:
    from fleet.agentctl import restart
    r = restart(_entry_or_die(a.agent))
    print("\n".join(r["notes"]))
    return {"ok": 0, "pending": 3}.get(r["status"], 1)


#: H5-mérés (2026-10-29): a fejlesztő ágens a `fleet --help`-et olvasta, de az összeolvasztás
#: eljárásához nem jutott el. Ez a sor minden `fleet --help` alján ott van.
MERGE_EPILOG = (
    "Ágens kivezetése, beolvasztása, feladatainak átadása, frissítése a legújabb Mentatra\n"
    "(retire / merge / hand over duties / upgrade an agent): ELŐSZÖR\n"
    "  fleet plan-merge --donor <régi> --recipient <fogadó>\n"
    "— lépések és ⛔ STOP-pontok (a tulajdonos igene nélkül semmi kifelé ható, semmi törlés).\n"
    f"Az eljárás: {PLUGIN_DIR / 'skills' / 'merge-agents' / 'SKILL.md'} (/merge-agents skill)."
)

#: Ezek után a parancsok után az operátor-skillek (merge-agents) a box Claude Code-jában is ott
#: vannak (symlink a helyi checkoutra; `fleet.operator_skills`).
LINK_SKILLS_AFTER = {"install", "join", "setup", "upgrade", "init"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fleet", description="Mentat fleet — always-on ágensek futtatása",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=MERGE_EPILOG)
    p.add_argument("--version", action="version", version=f"fleet {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("init", help="a registry-bejegyzés EGY parancsa a repóból (+ validate, előfeltételek, következő lépés)"); x.add_argument("agent", nargs="?", help="alapból a mentat.json agent.name-je, különben a repó könyvtárneve"); x.add_argument("--repo", default="."); x.add_argument("--model", default="opus"); x.set_defaults(fn=cmd_init)
    x = sub.add_parser("setup", help="EGY parancs: validate → join → preflight → install → híd → plugin → reconcile → doctor (0 kész · 3 függő · 1 hiba)"); x.add_argument("agent"); x.add_argument("--check", action="store_true", help="nem ír, csak megmondja, mi hiányzik"); x.add_argument("--no-tick", action="store_true", help="ne futtasson első ticket"); x.add_argument("--fix-claude-md", action="store_true", help="mint a join-nál"); x.add_argument("--plugin-source", metavar="local:<út>", help="helyi plugin-forrás; csak a nem commitolt settings.local.json-ba kerül"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_setup)
    x = sub.add_parser("auth", help="a shell CLAUDE_CODE_OAUTH_TOKEN-jét (vagy a stdin első sorát) átadja az ágens unitjának (0600)"); x.add_argument("agent"); x.add_argument("--from-systemd", action="store_true", help="a felhasználói systemd környezetében élő tokent használja (`systemctl --user show-environment`)"); x.set_defaults(fn=cmd_auth)
    x = sub.add_parser("stop", help="EGY ágens leállítása (csak a saját unitja/tmux-sessionje); a reconcile a timer egy periódusán belül visszaindítja"); x.add_argument("agent"); x.add_argument("--hold", type=int, metavar="PERC", help="karbantartási zár: addig nem indul vissza"); x.set_defaults(fn=cmd_stop)
    x = sub.add_parser("wait-up", help="megvárja, hogy a leállított ágens visszajöjjön (megmondja, mikor várható)"); x.add_argument("agent"); x.add_argument("--timeout", type=int, default=420, metavar="MP"); x.set_defaults(fn=cmd_wait_up)
    x = sub.add_parser("restart", help="EGY ágens újraindítása (zár feloldva) + postcheck"); x.add_argument("agent"); x.set_defaults(fn=cmd_restart)
    sub.add_parser("validate", help="registry-konzisztencia").set_defaults(fn=cmd_validate)
    c = sub.add_parser("capabilities", help="képességfa: a box ágenseinek jóváhagyott exportja (collect) és keresés (find --as)")
    cs = c.add_subparsers(dest="sub", required=True)
    x = cs.add_parser("collect"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_capabilities)
    x = cs.add_parser("find"); x.add_argument("--as", dest="as_agent", required=True); x.add_argument("--json", action="store_true")
    x.add_argument("query"); x.set_defaults(fn=cmd_capabilities)
    x = sub.add_parser("render", help="unit szövege a registryből"); x.add_argument("agent"); x.set_defaults(fn=cmd_render)
    x = sub.add_parser("install", help="unit + felügyelet telepítése, indítás, postcheck (0 kész · 3 függő · 1 hiba, visszaállítva)"); x.add_argument("agent"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_install)
    x = sub.add_parser("preflight", help="telepíthető-e a repó"); x.add_argument("agent"); x.set_defaults(fn=cmd_preflight)

    b = sub.add_parser("bridge", help="Telegram-híd"); bs = b.add_subparsers(dest="sub", required=True)
    x = bs.add_parser("install"); x.add_argument("agent"); x.set_defaults(fn=cmd_bridge_install)
    x = bs.add_parser("rollback"); x.add_argument("agent"); x.set_defaults(fn=cmd_bridge_rollback)
    bs.add_parser("status").set_defaults(fn=cmd_bridge_status)

    x = sub.add_parser("lock", help="karbantartási zár"); x.add_argument("agent"); x.add_argument("--ttl", type=int, default=120); x.set_defaults(fn=cmd_lock)
    x = sub.add_parser("unlock"); x.add_argument("agent"); x.set_defaults(fn=cmd_unlock)
    x = sub.add_parser("unquarantine", help="karantén feloldása (ok elhárítva)"); x.add_argument("agent"); x.set_defaults(fn=cmd_unquarantine)

    x = sub.add_parser("roster", help="ki van a flottában, mi fut"); x.add_argument("--host"); x.add_argument("--no-probe", action="store_true"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_roster)
    x = sub.add_parser("doctor", help="a négy jel ágensenként"); x.add_argument("agent", nargs="?"); x.add_argument("--fix", action="store_true"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_doctor)
    x = sub.add_parser("postcheck", help="restart utáni ellenőrzés"); x.add_argument("agent"); x.add_argument("--wait", type=int, default=90); x.set_defaults(fn=cmd_postcheck)
    x = sub.add_parser("reconcile", help="kívánt állapot érvényesítése (timer)"); x.add_argument("--observe", action="store_true"); x.add_argument("--agent"); x.add_argument("--fast", action="store_true", help="gyors út: csak a megerősítetten leállt processzt indítja (30 mp-es timer)"); x.set_defaults(fn=cmd_reconcile)

    x = sub.add_parser("join", help="egy repó belép a flottába"); x.add_argument("repo"); x.add_argument("--agent", required=True); x.add_argument("--brain", default=None); x.add_argument("--reducer", default=None); x.add_argument("--fix-claude-md", action="store_true", help="ha a CLAUDE.md nem tölti be az AGENTS.md-t, beírja"); x.set_defaults(fn=cmd_join)
    x = sub.add_parser("status", help="egy ágens elemei és szinergiái (mentat.json, .mentat/local.json, timerek)"); x.add_argument("agent"); x.add_argument("--repo"); x.add_argument("--json", action="store_true"); x.set_defaults(fn=cmd_status)
    x = sub.add_parser("upgrade", help="a repó fleet-fájljainak frissítése"); x.add_argument("repo"); x.set_defaults(fn=cmd_upgrade)
    x = sub.add_parser("release", help="a telepített release-tuple"); x.add_argument("--show", action="store_true"); x.set_defaults(fn=cmd_release)
    from fleet import ask_cli, login_cli, plan_merge, probe, retire   # ágens-összeolvasztás (2026-10-29)
    probe.add_parser(sub); login_cli.add_parser(sub); retire.add_parser(sub)
    ask_cli.add_parser(sub); plan_merge.add_parser(sub)
    from fleet import titok_cli   # titok-leltár és titok-kapu (H5, 2026-10-29)
    titok_cli.add_parser(sub)
    from fleet import outward_hold_cli   # kifelé-tartás (H5, 2026-10-29)
    outward_hold_cli.add_parser(sub)
    from fleet import registry_set   # registry-mező a tulajdonos igenjével (H5, 2026-10-29)
    registry_set.add_parser(sub)
    from fleet import plugin_install   # a /fleet:* plugin local scope-pal (2026-10-31)
    plugin_install.add_parser(sub)
    return p


def cmd_capabilities(a) -> int:
    from fleet import capabilities as caps
    if a.sub == "collect":
        out = caps.collect()
        print(json.dumps(out, ensure_ascii=False, indent=1) if a.json else
              "\n".join("%s: %s" % (k, v.get("error") or "%d tétel, %d kiszűrve" % (len(v["capabilities"]), v["dropped"]))
                        for k, v in out.items()) or "nincs ágens ezen a boxon")
        return 0
    try:
        res = caps.find(a.as_agent, a.query)
    except caps.Refused as e:
        print(json.dumps({"schema": 1, "error": str(e)}) if a.json else "fleet: %s" % e)
        return 2
    print(json.dumps(res, ensure_ascii=False) if a.json else
          "\n".join("%s · %s [%s] %s" % (r["agent"], r["id"], r["availability"], "; ".join(r["intent"]))
                    for r in res["results"]) or "nincs találat")
    return 0


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd in LINK_SKILLS_AFTER and not getattr(a, "check", False):
        from fleet.operator_skills import link_operator_skills
        for note in link_operator_skills():
            print(f"fleet: {note}", file=sys.stderr)
    try:
        return a.fn(a)
    except RegistryNotConfigured as e:
        print(f"fleet: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
