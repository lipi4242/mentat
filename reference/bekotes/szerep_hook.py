"""The guard hook entries in .claude/settings.json: written at init (mentat_scaffold.py)
and again by `bekotes.py szerepek`; one entry per event however often it runs."""
import json
import os
import pathlib
import re

TIMEOUT = 10  # seconds
GUARD = 'python3 -I "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_guard.py'  # -I: no PYTHONPATH, no user site
HINT = "szerep-őr hiányzik: futtasd az inicializálás 1. lépését vagy a BEKOTES 0. lépését"
# The hook is committed but the script is not (.mentat/ is git-ignored). A checkout without
# the tools is fail-closed: every tool is denied except fetching them again (step 1 curl).
_HAVE = '[ -f "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_guard.py ] || '
_DENY = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": HINT}})  # ASCII: no quote clash
_MISSING = ("import json,sys;d=json.load(sys.stdin);c=str((d.get('tool_input') or {}).get('command',''));"
            "ok=d.get('tool_name')=='Bash' and 'raw.githubusercontent.com/lipi4242/mentat/' in c;"
            "ok or print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', "
            "'permissionDecision': 'deny', 'permissionDecisionReason': %r}}))" % HINT)
GUARD_PRE = _HAVE + "{ python3 -c \"%s\" || echo '%s'; exit 0; }; %s" % (_MISSING, _DENY, GUARD)
GUARD_POST = _HAVE + "exit 0; %s --post" % GUARD
GUARD_STOP = _HAVE + 'exit 0; python3 -I "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_stop.py'  # fails open
GUARD_PROMPT = _HAVE + 'exit 0; python3 -I "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_prompt.py'  # records
GUARD_START = _HAVE + ("{ echo '{\"hookSpecificOutput\": {\"hookEventName\": \"SessionStart\", "
                       "\"additionalContext\": \"%s\"}}'; exit 0; }; %s --session-start" % (HINT, GUARD))
# Native layer next to the hook (deny wins over every allow; Read rules also cover cat/head/tail).
# ~/.claude is narrowed to memories, transcripts and credentials: this project's large tool
# output lives under ~/.claude/projects/<slug>/ and must stay readable.
NATIVE_DENY = ["Read(~/.ssh/**)", "Read(~/.config/**)", "Read(//**/.env*)",
               "Read(~/.claude/projects/*/memory/**)", "Read(~/.claude/projects/**/*.jsonl)",
               "Read(~/.claude/.credentials.json)", "Read(~/.config/*/claude-auth.env)"]


def install(repo):
    """Add the guard hooks to <repo>/.claude/settings.json; ValueError on a broken file."""
    path = pathlib.Path(repo) / ".claude" / "settings.json"
    try:
        s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        s = None
    if not isinstance(s, dict) or not isinstance(s.setdefault("hooks", {}), dict):
        raise ValueError(".claude/settings.json nem olvasható JSON-objektum")
    # onFailure "block" (Claude Code >= 2.1.295): a crash, timeout, missing python or bad JSON
    # blocks the call; without it a command hook fails OPEN.
    pre = {"type": "command", "command": GUARD_PRE, "timeout": TIMEOUT, "onFailure": "block"}
    want = {"PreToolUse": {"matcher": "*", "hooks": [pre]},
            "PostToolUse": {"matcher": "*", "hooks": [{"type": "command", "command": GUARD_POST, "timeout": TIMEOUT}]},
            "SessionStart": {"hooks": [{"type": "command", "command": GUARD_START, "timeout": TIMEOUT}]},
            "Stop": {"hooks": [{"type": "command", "command": GUARD_STOP, "timeout": TIMEOUT}]},
            "UserPromptSubmit": {"hooks": [{"type": "command", "command": GUARD_PROMPT, "timeout": TIMEOUT}]}}
    perms = s.setdefault("permissions", {})
    if not isinstance(perms, dict) or not isinstance(perms.setdefault("deny", []), list):
        raise ValueError(".claude/settings.json: permissions.deny nem lista")
    perms["deny"] += [r for r in NATIVE_DENY if r not in perms["deny"]]
    for event, entry in want.items():
        old = s["hooks"].get(event, [])
        if not isinstance(old, list):
            raise ValueError(".claude/settings.json: hooks.%s nem lista" % event)
        kept = []
        for e in old:  # drop earlier guard entries
            if isinstance(e, dict) and isinstance(e.get("hooks"), list):
                hs = [h for h in e["hooks"] if not (isinstance(h, dict)
                      and re.search(r"szerep_(guard|stop|prompt)\.py", str(h.get("command", ""))))]
                if not hs:
                    continue
                e = dict(e, hooks=hs)
            kept.append(e)
        s["hooks"][event] = kept + [entry]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# The 0.3.0 PreToolUse line: `[ -f …szerep_guard.py ] || { echo "…" >&2; exit 0; }` — a fresh
# clone (.mentat/ is git-ignored) passed every call; onFailure cannot see a 0 exit.
OPEN_IF_MISSING = re.compile(r'\|\| \{ echo "[^"]*" >&2; exit 0; \}')


def harden(repo):
    """F-39 for an existing install: onFailure "block" + a timeout on the guard's PreToolUse
    handler, and the 0.3.0 exit-0-when-missing line becomes GUARD_PRE (fail-closed); nothing
    else in the file changes. Returns how many handlers were changed."""
    path = pathlib.Path(repo) / ".claude" / "settings.json"
    if not path.exists():
        return 0
    s = json.loads(path.read_text(encoding="utf-8"))  # ValueError: a broken file stays as it is
    changed = 0
    for e in ((s.get("hooks") or {}).get("PreToolUse") or []) if isinstance(s, dict) else []:
        for h in (e.get("hooks") or []) if isinstance(e, dict) else []:
            if isinstance(h, dict) and "szerep_guard.py" in str(h.get("command", "")):
                before = dict(h)
                h.setdefault("timeout", TIMEOUT)
                h["onFailure"] = "block"
                if OPEN_IF_MISSING.search(str(h["command"])):  # 0.3.0: a missing script exited 0
                    h["command"] = GUARD_PRE
                changed += h != before
    if changed:
        _atomic_write(path, json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    return changed


def _atomic_write(path, text):
    """tmp in the same folder + os.replace: a crash leaves the old file or the new one, never half."""
    tmp = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="szerep_hook.py", description="--harden: F-39 for a 0.3.0 install")
    ap.add_argument("--harden", action="store_true", required=True)
    ap.add_argument("--repo", default=".")
    try:
        n = harden(ap.parse_args().repo)
    except ValueError as e:
        print("HIBA: a .claude/settings.json nem olvasható (%s); nem írtam át." % e)
        sys.exit(1)
    print("szerep-őr hook: %d kezelő kapott onFailure:block-ot és timeoutot (0 = már rendben volt, "
          "vagy nincs szerep-őr hook)." % n)
