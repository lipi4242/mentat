"""Is this repo deployable? The contract checked BEFORE anything is installed.

THE GAP THIS FILLS. `fleet validate` checks whether the registry is internally
consistent, `fleet doctor` whether the running fleet is healthy. Between them
sits the repo — the thing being deployed — and nothing looked at it. One real
deployment found its problems by running into them one at a time:
a trigger name the engine did not have (which would have produced an empty plan
with exit 0, i.e. a daily round that ran green forever and swept nothing), a
bridge default wrong for a dedicated group, an env file whose contract lived
only in someone's head.

WHAT THIS IS NOT. It does not judge whether the agent's job is well designed —
that part is irreducibly per-agent and takes the bulk of any build. It
answers the narrow question an operator must not have to answer from memory:
*can this be deployed at all?*

DELIBERATELY ABSENT CHECKS. An adversarial review of the design proposed a
nine-gate contract; four of those gates were theatre and were cut rather than
shipped:

  * "AGENTS.md <= 200 lines" — size is not quality, and it is gamed by pressing
    Enter less. It was first replaced by a required-headings check, which was
    run against the real fleet and failed EIGHT of nine agents — every brain
    written in Hungarian, because the required words were English. A gate that
    fails a working fleet is not strict, it is broken: it trains the operator
    to pass --skip, and then it protects nothing. Cut. That AGENTS.md exists at
    all is already audit criterion (c).
  * "tests green" as fleet law — a shallow suite always passes; real breakage is
    integration. It stays a scaffold default, not a gate.
  * "runbook is not a stub" — unmeasurable without a checklist to measure it
    against; `validate` already proves the file exists.
  * a full git-history secret scan on every run — expensive and noisy enough
    that it would be routinely skipped, and a gate people skip is worse than no
    gate because it still reads as green. It belongs at birth and at registry
    approval, not here.

Findings are strings, and the check ORDER is the order an operator would want to
fix them in: the repo first (cheap, local), then the registry, then the box.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from fleet.registry import is_dormant

#: Fields without which an agent cannot be rendered or run at all. Referential
#: integrity (does this secret/account/runbook EXIST) is `inventory.validate`'s
#: job and is not duplicated here — this asks only "is anything missing".
REQUIRED_FIELDS = ("agent", "unit", "session", "workdir", "model", "host")

#: Extra fields a ticking agent needs. A proactive agent without `loop_cmd` has
#: nothing to arm, and without `tick_period_s` every derived threshold in
#: liveness/watchdog/arming silently falls back to a default that is not its own.
REQUIRED_PROACTIVE_FIELDS = ("loop_cmd", "tick_period_s")

#: Where an agent's engine CLI may live. Agents differ legitimately: the newer
#: repos vendor the engine at the root, some keep it under scripts/anytime/v2,
#: and some agents (pure chat bots, operators) have no tick engine at all. Absence is
#: therefore NOT a finding — only a present engine that misbehaves is.
ENGINE_CLIS = ("entry.py", "scripts/anytime/v2/entry.py")

#: Timeout for the repo's own CLI. Generous: a cold import of a vendored engine
#: on a loaded box is slow, and a false "timed out" would teach people to pass
#: --skip.
CLI_TIMEOUT_S = 90


def local_box_key(boxes: list[dict]) -> str | None:
    """Which box are we ON, according to the registry.

    The fleet can span more than one box, and every check in this module reads
    the LOCAL filesystem. Running them against an agent that lives elsewhere
    reports its workdir and env file as missing — which is true here and
    meaningless (observed in production: preflight on one box declared the
    agents of another box unfit).

    Delegates to `registry.local_host` — FLEET_HOST env → ~/.config/fleet/host
    → the box whose `hostname` matches this machine → None. None means "not on
    any known box" (e.g. a developer machine).
    """
    from fleet.registry import local_host
    return local_host(boxes)


def is_checkable_here(entry: dict, local_box: str | None) -> bool:
    """Can this agent's repo and config be inspected from where we are?

    `None` (not on a known box, e.g. a developer machine) means "check anyway":
    refusing would make the module untestable in the one place people iterate
    on it, and a developer running it knowingly is not misled by the result.
    """
    if local_box is None:
        return True
    return entry.get("host") == local_box


def _run(cmd: list[str], cwd: Path, timeout: int = CLI_TIMEOUT_S):
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


# ── pure checks ───────────────────────────────────────────────────────────

def missing_fields(entry: dict) -> list[str]:
    """Pure: registry fields required to deploy this agent that are absent."""
    out = [f for f in REQUIRED_FIELDS if not entry.get(f)]
    if entry.get("proactive"):
        out += [f for f in REQUIRED_PROACTIVE_FIELDS if not entry.get(f)]
    bridge = entry.get("bridge") or {}
    if bridge.get("mode") == "sub-etha":
        out += [f"bridge.{f}" for f in ("unit", "version") if not bridge.get(f)]
    return out


def mode_findings(mode: int | None, path: str) -> list[str]:
    """Pure: an env file readable by anyone but its owner.

    `None` = the file is missing, which is a different finding raised by the
    caller — absence and exposure must not collapse into one message.
    """
    if mode is None:
        return []
    perms = mode & 0o777
    return ([] if perms == 0o600
            else [f"{path} is {oct(perms)}, must be 0600 — it holds a bot token"])


def token_collisions(fingerprints: dict[str, str | None]) -> list[str]:
    """Pure: agents sharing a bot token, from {agent: fingerprint}.

    Telegram allows exactly one `getUpdates` consumer per token; a second one
    makes the first lose messages intermittently — which looks like flakiness,
    not like a configuration error, and is therefore expensive to diagnose. We
    compare FINGERPRINTS, never tokens: this check must be impossible to turn
    into a way of printing a secret.
    """
    seen: dict[str, list[str]] = {}
    for agent, fp in sorted(fingerprints.items()):
        if fp:
            seen.setdefault(fp, []).append(agent)
    return [f"{' and '.join(agents)} are configured with the SAME bot token — "
            "only one can poll it"
            for agents in seen.values() if len(agents) > 1]


def fingerprint(token: str) -> str:
    """A short, non-reversible tag for a bot token. Never the token itself."""
    return hashlib.sha256(token.strip().encode()).hexdigest()[:16]


# ── I/O checks ────────────────────────────────────────────────────────────

def read_token_fingerprint(env_path: Path) -> str | None:
    """The bot token's fingerprint from an agent env file, or None.

    Reads the file but returns only a hash, so no caller — including a future
    one written in a hurry — can print a token by accident.
    """
    try:
        text = env_path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "TELEGRAM_BOT_TOKEN" and value.strip():
            return fingerprint(value.strip().strip('"').strip("'"))
    return None


def engine_cli(workdir: Path) -> str | None:
    """The agent's engine CLI, relative to its workdir, or None if it has none."""
    for rel in ENGINE_CLIS:
        if (workdir / rel).is_file():
            return rel
    return None


def engine_findings(workdir: Path, triggers: list[str]) -> list[str]:
    """The repo's own engine must validate, and every trigger must plan work.

    The second half is the one that would have caught a phantom `daily`
    trigger: the CLI accepted it, the engine had no such trigger, so the run
    produced an EMPTY PLAN and exit 0. A daily round would have gone green
    forever while sweeping nothing — the worst failure shape there is, because
    every signal says fine.
    """
    cli = engine_cli(workdir)
    if cli is None:
        # No engine is a legitimate shape (e.g. a pure chat bot), not a fault.
        # Reporting it would fail a third of a working fleet — see the module
        # docstring on why a gate that cries wolf protects nothing.
        return []

    out: list[str] = []
    r = _run(["python3", cli, "--validate"], workdir)
    if r is None:
        out.append(f"{cli} --validate could not be run")
    elif r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip().splitlines()
        out.append(f"{cli} --validate failed: " + (detail[-1] if detail else "?"))

    for trigger in triggers:
        r = _run(["python3", cli, "--dry-run", "--trigger", trigger], workdir)
        if r is None or r.returncode != 0:
            out.append(f"--dry-run --trigger {trigger} did not run cleanly")
            continue
        # The phantom-trigger signature is an empty plan with a zero exit AND
        # no stated reason. The "no stated reason" half is load-bearing and was
        # learned the hard way: run against the real fleet, this check accused
        # a release agent, whose dry-run had answered
        # `{"skipped": "lease-busy", "message": "..."}` — an engine that
        # understood the trigger perfectly and declined on purpose. An engine
        # that says WHY it planned nothing has demonstrated it knows the
        # trigger; that is exactly what a phantom trigger cannot do.
        if not (_plan_has_work(r.stdout) or _declined_on_purpose(r.stdout)):
            out.append(f"trigger {trigger!r} plans NO work and gives no reason — "
                       "is it a trigger the engine actually has?")
    return out


#: Keys by which an engine states that it understood the trigger and chose not
#: to plan (a held lease, a closed window, nothing due).
DECLINED_KEYS = ("skipped", "reason", "message", "note")


def _declined_on_purpose(stdout: str) -> bool:
    """Pure: did the engine explain why it planned nothing?"""
    import json as _json

    try:
        plan = _json.loads(stdout)
    except ValueError:
        return False
    return isinstance(plan, dict) and any(plan.get(k) for k in DECLINED_KEYS)


def _plan_has_work(stdout: str) -> bool:
    """Does this dry-run output describe at least one concern to run?

    Shape-tolerant on purpose: the engines differ across repos, and a check that
    demanded one exact JSON shape would fail on the next agent and get skipped.
    Any concern name in a plan/actions list counts.
    """
    import json as _json

    try:
        plan = _json.loads(stdout)
    except ValueError:
        # Not JSON — fall back to "did it name anything at all".
        return bool(stdout.strip())
    if isinstance(plan, dict):
        for key in ("plan", "actions", "concerns", "levels"):
            if plan.get(key):
                return True
        return False
    return bool(plan)


def preflight(entry: dict, *, home: Path | None = None,
              all_entries: list[dict] | None = None) -> list[str]:
    """Every reason this agent cannot be deployed yet. [] means go.

    Dormant agents return [] — a resting agent is not being deployed, and
    reporting it as unfit would train the operator to ignore this output.
    """
    if is_dormant(entry):
        return []

    home = home or Path.home()
    findings = [f"registry: missing {f}" for f in missing_fields(entry)]

    workdir = Path(str(entry.get("workdir", "")).replace("%h", str(home)))
    if not workdir.is_dir():
        findings.append(f"workdir {workdir} does not exist")
    else:
        if not (workdir / "AGENTS.md").is_file():
            findings.append(f"no AGENTS.md in {workdir} — the agent has no brain")
        triggers = entry.get("preflight_triggers") or _triggers_from_loop_cmd(entry)
        findings += engine_findings(workdir, triggers)

    if (entry.get("bridge") or {}).get("mode") == "sub-etha":
        env = home / ".config" / entry.get("agent", "") / "telegram.env"
        if not env.is_file():
            findings.append(f"{env} is missing — the bridge has no token to use")
        else:
            findings += mode_findings(env.stat().st_mode, str(env))
            if all_entries:
                fps = {e.get("agent", "?"): read_token_fingerprint(
                           home / ".config" / e.get("agent", "") / "telegram.env")
                       for e in all_entries if not is_dormant(e)}
                findings += [c for c in token_collisions(fps)
                             if entry.get("agent", "") in c]
    return findings


def _triggers_from_loop_cmd(entry: dict) -> list[str]:
    """The trigger a proactive agent's own loop command will actually use.

    Taken from the registry rather than guessed, because the registry is what
    systemd will type into the session. If the loop command names no trigger we
    return nothing rather than inventing one — a made-up trigger would be
    checked instead of the real one, which is worse than not checking.
    """
    cmd = entry.get("loop_cmd") or ""
    m = re.search(r"--trigger\s+([A-Za-z0-9_-]+)", cmd)
    return [m.group(1)] if m else []
