#!/usr/bin/env python3
"""Role guard: Claude Code PreToolUse / SessionStart hook for Mentat roles.

    szerep_guard.py                 PreToolUse: JSON on stdin, deny JSON on stdout
    szerep_guard.py --session-start SessionStart: pin the role, print context

Rule syntax and matching (our own fnmatch subset): see szerep_rules.py.
The role is resolved once (mentat_roles.role: MENTAT_ROLE if installed, else
roles.default) and pinned in .mentat/szerep/<session_id>. The repo root comes from CLAUDE_PROJECT_DIR, then this script's own
location (.mentat/bin/bekotes/), then the hook cwd. Any resolution error denies
everything. Before any role rule, szerep_dontes guards the working-folder boundary and dangerous
operations (ask interactively, deny headless); --post records the USER's consent. The guard prevents accidents; it is not a security boundary.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from szerep_pin import (brain_root, find_root, manifest, pinned_role, resolve,  # noqa: E402
                        role_file, safe_sid, write_pin)
from szerep_rules import GuardError, builtin_rules, match, parse_deny  # noqa: E402
from szerep_tiltott import grep_denied, read_rules, role_swept  # noqa: E402
import szerep_dontes  # noqa: E402


def deny_out(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def pre_tool_use(data):
    root = find_root(data)
    edge = root or boundary_root()
    if edge is None:
        return None
    first = szerep_dontes.decide(data, edge)  # every session, roles or not
    if root is None or (first and first["hookSpecificOutput"]["permissionDecision"] == "deny"):
        return first
    return role_rules(data, root) or first  # a role's deny beats the USER-ask


def role_rules(data, root):
    try:
        res = pinned_role(root, safe_sid(data.get("session_id")))
        if not res["role"]:
            return None
        builtin = builtin_rules(brain_root(root)) + read_rules(root, brain_root(root), res["role"])
        swept = grep_denied(root, brain_root(root), res["role"], data.get("tool_name", ""),
                            data.get("tool_input") or {}, data.get("cwd"))
        rules = parse_deny(role_file(root, res).read_text()) + builtin
        swept = swept or role_swept(root, brain_root(root), [r for r in rules if r.startswith("Read(")],
                                    data.get("tool_name", ""), data.get("tool_input") or {},
                                    data.get("cwd"), match)
    except (GuardError, OSError, ValueError, KeyError, TypeError) as e:
        return deny_out("A szerep nem oldható fel (%s), ezért minden eszköz tiltott. "
                        "Javítsd a szerepeket vagy indíts újra: MENTAT_ROLE=<név> claude" % e)
    if swept:
        return deny_out("A(z) %s szerep nem kereshet tiltott fájlt tartalmazó mappában (%s); "
                        "célzottan olvass: $BK olvas grep|show" % (res["role"], swept))
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    for rule in rules:
        if match(rule, tool, inp, root, fold=True, cwd=data.get("cwd")):  # case-insensitive disks
            return deny_out("A(z) %s szerep ezt nem teheti: %s. "
                            "Más szerephez indíts újra: MENTAT_ROLE=<név> claude" % (res["role"], rule))
    return None


def boundary_root():
    """The repo this vendored copy lives in (.mentat/bin/bekotes/), even before mentat.json."""
    here = pathlib.Path(__file__).resolve().parent
    return here.parents[2] if here.parent.name == "bin" and here.parents[1].name == ".mentat" else None


def post_tool_use(data):
    root = find_root(data) or boundary_root()
    if root is not None:
        szerep_dontes.post(data, root)


def session_start(data):
    root = find_root(data)
    if root is None:
        return None
    sid = safe_sid(data.get("session_id"))
    try:
        res = resolve(root)
    except GuardError as e:
        return "A szerep nem oldható fel (%s): a szerep-őr minden eszközt tilt." % e
    if not res["role"]:
        return None
    if sid:
        write_pin(root, sid, res["role"])
        ignore = root / ".gitignore"
        text = ignore.read_text() if ignore.exists() else ""
        if ".mentat/" not in text.split():
            ignore.write_text(text + ("" if text.endswith("\n") or not text else "\n") + ".mentat/\n")
    default = (manifest(root).get("roles") or {}).get("default")
    if res["role"] == default:
        return None
    return "Szerep ebben a futásban: %s (%s) — utasításai: %s" % (
        res["role"], res["source"], res["file"])


def f41_note(data):
    import szerep_kapu_id  # F-41: cache the identifiers once per session (never raises)
    root = find_root(data)
    return szerep_kapu_id.session_start(root) if root else None


def main(argv):
    if "--post" in argv:
        try:
            post_tool_use(json.loads(sys.stdin.read() or "{}"))
        except Exception:  # noqa: BLE001 - recording consent never blocks a finished call
            pass
        return 0
    session = "--session-start" in argv
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except ValueError:
        if session:
            ctx = "A hook-bemenet érvénytelen: a szerep-őr minden eszközt tilt."
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                     "additionalContext": ctx}}))
        else:
            print(json.dumps(deny_out("Érvénytelen hook-bemenet, ezért az eszköz tiltott.")))
        return 0
    if session:
        try:
            ctx = " ".join(x for x in (session_start(data), f41_note(data), __import__("szerep_start_sched").note(data)) if x)
        except Exception as e:
            ctx = "A szerep-őr indítási hibája (%s): minden eszköz tiltott lesz." % e
        if ctx:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                     "additionalContext": ctx}}))
        return 0
    try:
        out = pre_tool_use(data)
    except Exception as e:  # any failure denies: safe default
        out = deny_out("A szerep-őr hibája (%s), ezért az eszköz tiltott." % e)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
