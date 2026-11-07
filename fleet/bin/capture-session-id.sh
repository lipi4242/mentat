#!/bin/sh
# SessionStart hook — pin an AGENT session's id so a restart can `claude --resume` it.
#
# Fires on every session start, but is a strict no-op unless FLEET_AGENT (or THUFIR_AGENT) is set
# (which only the deploy systemd unit's ExecStart wrapper exports). This keeps
# ad-hoc dev sessions from overwriting an agent's pinned id, even when they share
# the same working directory (e.g. two agents in one ~/agent-repo).
#
# Registered as a user-level SessionStart hook in ~/.claude/settings.json.
# Always exits 0 — a hook failure must never block a session from starting.

# Older units (fleet-ops) export THUFIR_AGENT instead; both are served by this one hook.
AGENT="${FLEET_AGENT:-${THUFIR_AGENT:-}}"
[ -n "$AGENT" ] || exit 0
[ -n "${CLAUDE_CODE_SESSION_ID:-}" ] || exit 0

# A forked / background-agent session spawned FROM this agent inherits FLEET_AGENT,
# so the two guards above don't stop it from clobbering the pinned id with its own
# ephemeral session id (this is what crash-looped an agent on 2026-07-20: a bg fork
# pinned its id, every restart then `--resume`d a bg-held session and died). There
# is no documented SessionStart signal for a fork, so walk the process ancestry:
# a forked/background session's claude runs with --fork-session, or under a
# `bg-pty-host` / `daemon run` supervisor — the top-level agent session never does.
_pid=$PPID
_depth=0
while [ "${_pid:-0}" -gt 1 ] && [ "$_depth" -lt 12 ]; do
    _cl=$(tr '\0' ' ' < "/proc/$_pid/cmdline" 2>/dev/null)
    case "$_cl" in
        *--fork-session*|*bg-pty-host*|*"daemon run"*) exit 0 ;;
    esac
    _pid=$(ps -o ppid= -p "$_pid" 2>/dev/null | tr -d ' ')
    [ -n "$_pid" ] || break
    _depth=$((_depth + 1))
done

# A kimerült restart-keret az ágens kontextusába (a hook stdoutja): egy sor, vagy semmi.
_root=$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")/.." 2>/dev/null && pwd)
[ -n "$_root" ] && PYTHONPATH="$_root/src" python3 -m fleet.budget "$AGENT" 2>/dev/null

dir="$HOME/.config/$AGENT"
mkdir -p "$dir" 2>/dev/null || exit 0
printf '%s' "$CLAUDE_CODE_SESSION_ID" > "$dir/session.id" 2>/dev/null || exit 0
exit 0
