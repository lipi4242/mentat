# fleet guide

The details behind the [README](../../README.md): the registry, the layers, how supervision decides, what runs on the box, and the tests.

## The registry

The registry says WHERE and HOW each agent runs. It is not part of this
repository: it lives in a directory you own. `fleet` finds it in this order:

1. the `FLEET_REGISTRY` environment variable;
2. the `~/.config/fleet/registry` file (one line: the directory path);
3. otherwise it stops with an error ("no registry configured"). There is no
   silent default.

| file | what it describes |
|---|---|
| `agents.json` | where and how an agent runs: host, unit, session, `rc_name`, `status` (`active`/`dormant`), cadence, bridge, `claude_account` |
| `boxes.json` | the machines |
| `accounts.json` | external account identifiers, no secrets |
| `runbooks/` | one runbook per agent |
| `units/` | optional hand-written units (`unit_source: file`) |

`examples/registry/` is a complete example with made-up agents; `fleet init`
writes the minimum for you (`~/.config/fleet/registry.d`). Secrets (tokens,
keys) never go into the registry: a bot token lives on the box in
`~/.config/<agent>/telegram.env` (mode 0600).

## Layers

| layer | where | what it does |
|---|---|---|
| **Runner** | `src/fleet/` (Python, stdlib only), `bin/fleet` | `init`, `setup`, `validate`, `preflight`, `install`, `bridge`, `reconcile` (timer), `postcheck`, `doctor`, `roster`, `stop`/`wait-up`/`restart`, `lock`/`unlock`/`unquarantine`, `join`/`upgrade`, `status`, `release`, `secrets` |
| **Bridge** | `bridge/` (Node.js) | Telegram to tmux: `bridge.mjs` (poller, inbox, health), `send.mjs` (plain text; `--html` for filtered formatting) |
| **Plugin and templates** | `plugin/`, `templates/` | Claude Code skills and a SessionStart hook; unit template, drop-in, `rules/fleet.md.tmpl`, systemd timers |

The runner only reads the registry and uses only the standard library. The
bridge is Node.js, but the runner never imports it: it writes a unit for it.

## Supervision: five signals

| signal | source | when it is bad |
|---|---|---|
| **process** | is `claude` running with the expected `--remote-control <name>` | restart (3 per hour), then postcheck |
| **schedule** | `last-tick.json` or the tick marker in the transcript; for fleet-scheduled agents, measured against the `fleet-tick-<name>.timer` period | re-arm (claude loop only); alert after 12 periods (or `silence_after_s`) |
| **channel** | the bridge's `health.json` and 409 errors in the journal | kill the poller or restart the bridge (with a budget) |
| **RC** (optional) | Remote Control events in the transcript, an event rather than a state | report; if it cannot be measured it is `n/a` and does not affect the exit code |
| **auth** | an `authentication_failed` record in the transcript with no real reply after it | alert (a restart does not cure it): `claude auth login` on that box |

Every signal has an `unknown` value, which is neither `down` nor `ok`.
`fleet doctor` rates each signal `healthy`, `pending`, `unknown` or
`unhealthy`; an agent gets its worst signal and only a full `healthy` exits 0.
A restart counts as done when the **postcheck** is green: a new process
generation, no telegram-plugin poller, no 409, auth alive, and a tick that
landed AFTER the restart (`pending` within the grace period, a failure after
it). Two failed postchecks put the agent in quarantine with an alert for a
human to lift.

`dormant` is a desired state: reconcile stops and disables what runs. A bare
`systemctl disable` does not tell the supervisor anything.

## What runs on the box

| timer | period | what it does |
|---|---|---|
| `fleet-reconcile` | `templates/systemd/fleet-reconcile.timer` | the ONE controller: desired state from the registry plus postcheck, OOM protection (-600), tick re-arm, duplicate alerts |
| `fleet-reconcile-fast` | 30 s | fast path (`reconcile --fast`): restarts only a claude process missing in two consecutive observations (about 1 minute); bridge, alerts and re-arm stay on the full round |
| `fleet-tick-<agent>` | the engine's schedule | the engine's tick entry point, when `join` took over scheduling |

Only the engine writes the heartbeat; supervision reads the transcript age and
`last-tick.json`. Templates live under `templates/systemd/`; `fleet install`
substitutes the checkout path. If the same agent (by the registry's `host`)
also runs on THIS machine, reconcile and doctor raise an alert. Ownership is
the `~/.config/fleet/controller` file (`reconcile`); without it reconcile only
observes. The box key is `FLEET_HOST` or `~/.config/fleet/host`, otherwise the
`hostname` in `boxes.json`; an unknown machine has no default box.

## Secrets on a shared box

All agents on a box share one Unix user, so any agent can read another's keys and
transcripts. `fleet secrets` keeps values out of every Claude context:

| command | what it does |
|---|---|
| `fleet secrets scan --agent A [--agent B]` | names, places, formats and key names of the secret files (repo, `~/.config/<a>/`, `~/.claude-<a>/`, `<repo>/.mentat/`, unit `EnvironmentFile=`), never values; writes `~/.mentat/titkok/leltar.json` (0600) and installs the secrets gate |
| `fleet secrets approve --item OP:NAME:FROM:TO:WHY --owner-text "…"` | itemised owner approval, at most 60 minutes, each item usable once |
| `fleet secrets move\|copy --name K --from X --to Y --approval ID` | moves one key in-process, 0600, atomic, no symlinks; receipt in `~/.mentat/titkok/nyugtak.jsonl` |
| `fleet secrets audit [--repo DIR]` | did an inventoried value leak into a transcript, a repo or its git history (file:line only) |
| `fleet secrets hook install\|status` | the secrets gate (PreToolUse, deny only) in every `~/.claude*/settings.json` of the box |

The gate denies opening an inventoried or secret-named file, another agent's
transcript, and dumping the environment, also through `cat`/`sed`/`python`/`cp`/`ln`/globs.
v1 limits: same Unix user, the approval file is agent-writable, and a determined actor
can still bypass a hook. v2: sandbox denyRead, one Unix user per agent, bridge-signed
approvals, a `fleet secrets run --as` wrapper.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m unittest discover -s src/fleet -p 'test_*.py' -q
node --test "bridge/test/*.test.mjs"
FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
```

The Python tests import `pytest` as well (they run under both unittest and
pytest), so install it. The registry consistency tests
(`tests/test_registry_consistency.py`, `tests/test_registry_runbook_egyezes.py`)
check the example registry by default; point `FLEET_REGISTRY` at your own to
run them against it.

## Not included on purpose

- Your fleet's own data (registry, runbooks, ops notes): keep it in a
  directory or repository you own.
- Room-based agent-to-agent messaging and a dedicated fleet-controller agent;
  the native Claude Code channel (`ListAgents` / `SendMessage`) replaced them.
  From version 2.0 the bridge only keeps a delivery log
  ([`bridge/docs/delivery-log.md`](../../bridge/docs/delivery-log.md)).
