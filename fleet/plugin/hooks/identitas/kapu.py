#!/usr/bin/env python3
"""„Identitás kifelé” kapu (F-41) — referencia-prototípus a bootstrap szerep-őréhez.

    decide(tool, inp, cwd, ids, allow) -> None | {"azonosito": [...], "cel": [...]}
    kapu.py --hook           PreToolUse: JSON a stdin-en, ask (interaktív) / deny (headless) a stdout-on
    kapu.py --session-start  SessionStart: az azonosítók cache-be írása (tarolo.py)
    kapu.py --hook --instance plugin   plugin-példány: hátrébb lép, ha a felhasználói kapu fut
    MENTAT_ID_KAPU=ask|deny  a mód kényszerítése (a Macen: ask, auto módban is)

Akkor szól, ha egy hálózatra író hívás szövegében (vagy az általa olvasott helyi
fájlban) a felhasználó azonosítója áll, és van olyan cél, ami nincs az első-fél
allowlisten. Ismeretlen cél = nem első fél. A bootstrapben ez a szerep_kapu egy új
fajtája lesz („identitas”), és a szerep_dontes headless-logikáját használja.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elsofel  # noqa: E402
import halozat  # noqa: E402
import ident  # noqa: E402
import tarolo  # noqa: E402

UNATTENDED = {"bypassPermissions", "dontAsk", "auto"}


def decide(tool, inp, cwd, ids, allow):
    if tool in elsofel.LOCAL_TOOLS or allow.tool_ok(tool):
        return None
    out = halozat.outbound(tool, inp, cwd)
    if not out.net:
        return None
    found = ids.find(out.text)
    if not found:
        return None
    third = sorted(h for h in out.hosts if not allow.host_ok(h)) or ([] if out.hosts else ["<ismeretlen cel>"])
    if not third:
        return None
    return {"azonosito": found, "cel": third}


def headless(data, cwd):
    forced = os.environ.get("MENTAT_ID_KAPU", "")
    if forced in ("ask", "deny"):
        return forced == "deny"
    return (data.get("permission_mode") in UNATTENDED or bool(os.environ.get("MENTAT_HEADLESS"))
            or (pathlib.Path(cwd) / ".claude" / "fleet.json").exists()
            or os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"))


def _out(decision, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def _unparsed(data, cwd, phase, e):
    """The analysis itself failed: whether the call is local cannot be told, so it is never
    allowed. Interactive: ask, saying so; headless: deny. The exception is logged (no command text).
    A real gate fault (missing module, unreadable config) is not this: that still blocks."""
    tarolo.log_error(phase, e, (data.get("tool_input") or {}).get("command", ""))
    what = ("az identitás-kapu nem tudta elemezni ezt a hívást (%s, %s), ezért nem tudja eldönteni, "
            "kimegy-e azonosító, vagy ír-e a kapu fájljaira; napló: %s" % (phase, type(e).__name__, tarolo.ERRLOG))
    if headless(data, cwd):
        return _out("deny", "Headless futás: %s. Kérdezd meg a FELHASZNÁLÓt a csatornáján." % what)
    return _out("ask", "A FELHASZNÁLÓ jóváhagyása kell: %s." % what)


def hook(data, ids=None, allow=None):
    cwd = data.get("cwd") or os.getcwd()
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    try:
        prot = tarolo.touches_protected(tool, inp, cwd)
    except Exception as e:  # noqa: BLE001 - the parser's bug: never allow, ask (headless: deny)
        return _unparsed(data, cwd, "vedett", e)
    if prot and prot.startswith("beallitas:"):
        if headless(data, cwd):
            return _out("deny", "Headless futás: a Claude-beállítást (%s) nem írhatod." % prot[10:])
        return _out("ask", "A FELHASZNÁLÓ jóváhagyása kell: a Claude-beállítás (%s) írása a kaput is "
                           "kikapcsolhatja." % prot[10:])
    if prot:
        return _out("deny", "Az identitás-kapu fájljához (%s) csak a FELHASZNÁLÓ nyúlhat, kézzel." % prot)
    if ids is None:
        ids, logins = tarolo.load(cwd)
        allow = allow or elsofel.Allow.load(ids, gh_logins=logins)
    allow = allow or elsofel.Allow.load(ids)
    try:
        hit = decide(tool, inp, cwd, ids, allow)
    except Exception as e:  # noqa: BLE001
        return _unparsed(data, cwd, "halozat", e)
    if not hit:
        return None
    what = "a felhasználó azonosítója (%s) menne ide: %s" % (", ".join(hit["azonosito"]), ", ".join(hit["cel"]))
    if headless(data, cwd):
        decision, reason = "deny", (
            "Headless futás, itt senki nem hagyhatja jóvá — %s. Ne keress kerülőutat (kódolás, "
            "változó, fájl): hagyd ki az azonosítót — a polite-pool, a User-Agent és a mailto "
            "mező üresen marad, az API-k nélküle is működnek —, vagy kérdezd meg a FELHASZNÁLÓt "
            "a csatornáján." % what)
    else:
        decision, reason = "ask", "A FELHASZNÁLÓ jóváhagyása kell — %s. Harmadik félnek megy." % what
    return _out(decision, reason)


def main(argv):
    if "--session-start" in argv:
        try:
            tarolo.save(json.loads(sys.stdin.read() or "{}").get("cwd"))
        except Exception:  # noqa: BLE001 - a cache hiánya csak lassít, a PreToolUse élőben olvas
            pass
        return 0
    if "--hook" not in argv:
        print(__doc__)
        return 2
    try:
        data = json.loads(sys.stdin.read() or "{}")
        # dupla kérdés ellen: a plugin-példány átadja a hívást a felhasználói kapunak
        out = None if "plugin" in argv and tarolo.user_gate_active() else hook(data)
    except Exception as e:  # noqa: BLE001 - hibánál nem engedünk át (F-39)
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": "identitás-kapu hiba (%s)" % type(e).__name__}}
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
