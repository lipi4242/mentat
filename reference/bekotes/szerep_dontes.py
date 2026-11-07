"""The guard's decision before any role rule: boundary, dangerous operations, consent, log.

decide(data, root) -> hook output or None (PreToolUse); post(data, root) (PostToolUse).
Interactive: "ask", and Claude Code asks the USER. Headless (-p/SDK, bypass/dontAsk/auto
mode, a fleet agent on a Telegram bridge, MENTAT_HEADLESS): "deny", with a request to ask the
USER on their channel. What the USER approved goes to the consent list in post(), which
runs only after the asked call really ran: a file exactly (with read or write), a folder for
this session only, a zone root (HOME, /Users/<x>, config root) never. This is a heuristic accident guard; the native
permissions.deny rules in .claude/settings.json are the harder layer.
"""
import os
import pathlib

import szerep_engedely
import szerep_kapu
import szerep_kint
import szerep_naplo
import szerep_szoveg as szoveg

UNATTENDED = {"bypassPermissions", "dontAsk", "auto"}
def headless(data, root):
    return (data.get("permission_mode") in UNATTENDED
            or (pathlib.Path(root) / ".claude" / "fleet.json").exists()
            or bool(os.environ.get("MENTAT_HEADLESS"))
            or os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"))


def _hook(decision, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def _call(data, root):
    return (data.get("tool_name", ""), data.get("tool_input") or {},
            data.get("cwd") or str(root))


def decide(data, root):
    tool, inp, cwd = _call(data, root)
    bounced = __import__("szerep_kuldes").check(data, root)  # a bridge agent's reply: the Stop hook's checks
    if bounced:
        return _hook("deny", bounced)
    hit = szerep_kapu.protected(root, tool, inp, cwd)
    if hit:
        szerep_naplo.write(root, tool, [hit], "deny", "engedelylista")
        return _hook("deny", "Ezt (%s) az ágens nem írhatja: az engedélylistát és a naplót a FELHASZNÁLÓ "
                             "jóváhagyása, a képesség-nyugtát a `mentat_brain.py where`, az identitás-kapu "
                             "fájljait a FELHASZNÁLÓ kézzel írja; nem másolható és nem törölhető." % hit)
    kinds = szerep_kapu.dangerous(root, tool, inp, cwd)
    outs = szerep_kint.outside(root, tool, inp, cwd, data.get("session_id"))
    need = [p for p, _, ok in outs if not ok]
    if not kinds and not need:
        if outs:
            szerep_naplo.write(root, tool, [p for p, _, _ in outs], "allow", "engedely")
        return None
    tx = lambda key, *a: szoveg.text(root, key, *a)  # noqa: E731 — in the brain's language
    what = "; ".join([szoveg.kind(root, k) for k in kinds] + (["%s: %s" % (tool, ", ".join(need))] if need else []))
    if "elsofel" in kinds:  # the USER sees where each line comes from (CISO #84)
        import szerep_kapu_id
        what += " (%s)" % szerep_kapu_id.allowlist_detail(root, inp)
    for k, route in (("titok", "secret"), ("post", "final"), ("db-iras", "db"), ("beallitas", "own"), ("rm-kivul", "rm"),
                     ("force-push", "push"), ("env", "env"), ("git-config", "gitcfg")):
        if k in kinds:  # the guard names the route that stays open
            what += tx(route)
    what += tx("out") if need else ""
    why = tx("why_out") if need else tx("why")
    decision = "deny" if headless(data, root) or {"uj-kepesseg", "szerver"} & set(kinds) else "ask"
    szerep_naplo.write(root, tool, need, decision, ",".join(kinds + (["kivuli"] if need else [])))
    if "uj-kepesseg" in kinds:  # interactive too: the agent resolves it itself, the USER is not asked
        return _hook("deny", tx("self", what))
    if "szerver" in kinds:  # the agent resolves it itself: the tool returns with the URL
        return _hook("deny", tx("server", what))
    if decision == "deny" and "identitas" in kinds:
        return _hook("deny", tx("ident", what))
    if decision == "ask":
        return _hook("ask", tx("ask", what, why))
    return _hook("deny", tx("headless", what, why))


def post(data, root):
    """After an asked call ran (the USER approved it): its outside paths become consent."""
    if headless(data, root):
        return
    tool, inp, cwd = _call(data, root)
    sid = data.get("session_id")
    need = [(p, op) for p, op, ok in szerep_kint.outside(root, tool, inp, cwd, sid) if not ok]
    keep = [(p, op, os.path.isdir(p)) for p, op in need if not szerep_kint.is_root(p)]  # B-1
    if keep:
        szerep_engedely.record(root, keep, tool, sid)
    if need:
        szerep_naplo.write(root, tool, [p for p, _ in need], "jovahagyva", "kivuli")
