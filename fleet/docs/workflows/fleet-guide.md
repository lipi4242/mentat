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
| `fleet secrets scan --agent A [--agent B]` | names, places, formats and key names of the secret files (repo, `~/.config/<a>/`, `~/.claude-<a>/`, `<repo>/.mentat/`, unit `EnvironmentFile=`), never values; writes `~/.mentat/titkok/leltar.json` (0600). It does NOT install the gate and never turns on merge mode; if the gate is live and the new inventory would deny an agent's essentials, the old inventory stays. `--dry-run`: table only |
| `fleet secrets approve --item OP:NAME:FROM:TO:WHY --owner-text "…"` | itemised owner approval, at most 60 minutes, each item usable once |
| `fleet secrets move\|copy --name K --from X --to Y --approval ID` | moves one key in-process, 0600, atomic, no symlinks; receipt in `~/.mentat/titkok/nyugtak.jsonl` |
| `fleet secrets audit [--repo DIR]` | did an inventoried value leak into a transcript, a repo or its git history (file:line only) |
| `fleet secrets hook install [--dry-run\|--force]\|status` | the secrets gate (PreToolUse, deny only) in every `~/.claude*/settings.json` of the box. First an essentials probe: every agent's core paths (Telegram send in both shapes, `mentat-todo me/changes`, the `~/.config/<a>/jobs/` scripts, `git status/commit/push`, reading its own engine and review state) through the CANDIDATE gate, and whether a bridged agent's unit carries `TELEGRAM_BOT_TOKEN` (by name); a red agent means nothing is written. Then a canary: one root, re-probe, then the rest |

What goes into the inventory: a secret-like name, or content evidence (a private key, a secret-named
key/field with a value) — file mode alone never. A private unknown file without evidence is
"to review": listed, not denied. A name-based (suspect) denial asks the agent to report it, not to
work around it; a recursive grep can exclude a folder with `grep -r --exclude-dir=<dir>`.

### The agent runtime contract

- **Env:** the unit's pane shell (`ExecStart … /bin/sh -c`) sources the env files — under tmux,
  `EnvironmentFile=` alone does not reach claude. Order: for a bridged agent the bridge's
  `telegram.env` (`bridge.env_file`) FIRST, then the registry `env_files` / `env_file` (the agent's own
  file overrides shared keys), then `claude-auth.env` and `.mentat/model.env`. `FLEET_AGENT` always.
- **Sending:** `node ~/.config/<a>/sub-etha/send.mjs --chat <id> [--reply-to <id>] -- "text"` or
  `--text-stdin`; the token comes from that env, the agent never sources telegram.env. Without a
  token send.mjs writes a `missing_token` notice to the delivery log and the doctor turns red.
- **May read:** its own repo and state (`data/state/`, the engine's and review's state files), and run
  its own `~/.config/<a>/jobs/` scripts; it may NOT read key files, inventoried files, another agent's
  transcripts, or dump the environment.
- **Check:** `fleet doctor <a>` runs the essentials through the installed gate and checks the token
  name in the unit's env files. Box-wide commands (`hook install`, `scan`, `merge-mode on`,
  `install`) go through `--dry-run` first.

The gate denies opening an inventoried or secret-named file, another agent's
transcript, and dumping the environment, also through `cat`/`sed`/`python`/`cp`/`ln`/globs.
v1 limits: same Unix user, the approval file is agent-writable, and a determined actor
can still bypass a hook. v2: sandbox denyRead, one Unix user per agent, bridge-signed
approvals, a `fleet secrets run --as` wrapper.

### Capability, central fleet check, canary, release lag

- **Capability probe** (`kepesseg.py`): the doctor and every postcheck (restart, install,
  box-upgrade) also RUN the core paths, bounded (20 s per step, no Telegram call): `send.mjs --dry-run
  --chat $TELEGRAM_GROUP_CHAT_ID` with the unit's env files (token present and well-formed, chat,
  flags, length gate, writable delivery log), `mentat-todo me` (if the box has `~/.config/todo/env`),
  the agent's own state files, and `git status` in its repo. Any failure is red; in a postcheck it is
  `failed` with `capability_only` (a restart does not fix it, so no quarantine).
- **Central fleet check (a 1.0 capability), no separate alert bot:** the reconcile probes
  each agent at most every 15 minutes and every 10 minutes reports the results (plus box name,
  fleet version, release lag) to the Mentat Admin `flotta` plugin, configured in
  `~/.config/fleet/flotta.env` (`FLOTTA_URL` + `FLOTTA_TOKEN`, a box token whose only scope is
  `flotta:report`; never printed). A red check opens one incident per (agent, check) there; the
  lowest-rank manager (responsible agent) whose scope covers it and who is not down itself gets it as a todo task (`[flotta] …`, the `flotta-incidens` skill) and
  writes its attempts as comments; the next green report resolves it and closes the task. A box that
  does not report for 30 minutes opens a dead-man incident. A Worker cron mails the owner (no LLM in
  the path): after 60 minutes, at once if it concerns a manager and no healthy deputy is left, after 2
  red reports if no manager covers it, every 6 hours while open, and a short "Megoldva" on
  resolve. A failed report (10 s timeout) never breaks the reconcile: the red capability then lands in
  `~/.config/fleet/state/alerts-undelivered.jsonl`, the doctor's box line is red while it is there and
  shows `jelentés: elavult`; without the file it says `jelentés: kikapcsolva`. A red capability never
  goes through the failing agent's own bridge. Setup: `admin/docs/plugins/flotta/INSTALL.md`.
- **Fleet-manager role (flotta-menedzser).** Managers are listed in the versioned `fleet/managers.json`
  (fleet-ops; example `fleet/examples/managers.json`) and published with `fleet managers publish`,
  using a separate `flotta:config` token. The chain for a target is ordered `agent:` > `box:` > `*`,
  then rank, then the handle. It contains only managers that can reach the target (v1: their own
  box) and are fit to repair.

  The manager claims (`fleet incident claim`) and gets a 30-minute window and a fencing token. It
  repairs only through `fleet repair-exec` (an allowlist; lock → Worker check → intent → execute →
  result), and the incident closes only through `repair-exec … postcheck` with a verification
  nonce. When nobody claims, the window expires, or the manager becomes unfit, the next manager
  gets the incident; when the chain is empty or exhausted, a human does (e-mail).

  The report carries each agent's last executed tick (`last-tick.json`, written only by the tick).
  A desktop member (`supervision: none`) reports from its own session with `fleet flotta-report`.
  The tick timer skips while the agent has a `fleet lock`.

  Design: `fleet/docs/design/2026-11-08-flotta-menedzser.md` (monorepo); skill: `flotta-incidens`.
- **Canary for user-level settings** (`kanari.py`): writers of `~/.claude*/settings.json` hooks,
  `skills/` links and `claude plugin …` state (first-run seeding, operator skills, plugin install,
  the secrets gate) write the first root that hosts an agent, probe those agents, roll back on a NEW
  red, then the rest, and record a fingerprint. The doctor's box line warns when a root changed
  without a recorded canary run; after a manual change: `fleet canary record`.
- **Todo wake-up:** when the ball lands on an agent in the todo, it learns within a
  minute, not at the next hourly tick. The Telegram bridge (no LLM) polls `GET /changes?for=<handle>`
  every 20 s (at most 60 s, `BRIDGE_TODO_POLL_MS`) with the box todo config (`~/.config/todo/{env,
  handles,<handle>.token}`, the token is never printed), keeps its own cursor in
  `telegram-state/todo-state.json`, skips the agent's own writes, and injects ONE line in the Telegram
  style: `[Todo | ABC-12 | kiadta: thufir_mac | wake=<seq>]: cím: «<title>»` (structured fields only, the title cleaned and clipped to ~80 chars and marked as DATA; never a comment body — the agent reads the item itself; `mentat-todo ack <key>` is the receipt for "seen, nothing to do" and wakes nobody) (a list when several land within
  a minute; queued like Telegram while the agent is busy). It wakes on: issued to it, handed back to it,
  a mention, awaiting its acceptance, a comment where it holds the ball; never on bare field changes or
  traffic between others. Agents may talk in comments without limit; only an obvious runaway (8
  content-free comments from 2+ authors on one item in 10 minutes) is collected for 5 minutes, and that
  always alerts (`todo_runaway` notice + a group line) — nothing is dropped. Receipt: the line shows up
  in the transcript (3.2) and the agent writes on the item (`todo_wake_handled`); a wake without a
  write after 30 minutes is `MEGVÁLASZOLATLAN chat=todo` in `delivery.mjs`. Health: the capability probe
  reads `todo_last_poll_ok`, `todo_last_wake_latency_ms`, `todo_unhandled` from the bridge's
  `health.json` (`kepesseg_todo.py`); a poll older than 10 minutes or an unhandled wake is red
  (`todo-ebresztes` key) and becomes an incident in the central fleet check. Turn off per agent:
  `BRIDGE_TODO=off`. **Desktop (own computer, no bridge) gets the same:** the fleet plugin's
  SessionStart + UserPromptSubmit hook runs `plugin/hooks/todo/todo-once.mjs`, a byte-identical copy of
  the bridge code (`bridge/test/todo-plugin-copy.test.mjs` guards it): same line, same relevance
  filter, own writes excluded, coalescing (everything new since the last run is one line), receipt
  bookkeeping and health (`~/.local/state/mentat/todo/<agent>/health.json`; the session says when the
  last successful poll is older than 10 minutes). **The one inherent difference: a closed desktop
  session cannot be woken** — the events wait until someone writes to the session or opens a new one.
  Needs `node` on the PATH (the session start says so if it is missing).
- **Release lag:** the box line compares `git describe --tags` of the checkout with the newest public
  `v*` tag (`git ls-remote`, cached 6 h); offline means "not measurable", never red.

### Tick gate (release agents first)

A proactive agent's session cron costs a full LLM turn per tick, even when there is nothing to do.
The **tick gate** puts a non-LLM precheck in front of it: a per-agent systemd user timer
(`fleet-gate-<agent>.timer`, rendered from the registry `tick_gate` field by `fleet install` or
`fleet tick-gate install <agent>`) runs `fleet tick-gate run <agent>`. Only when there is work does it
type the registry `tick_cmd` into the pane (literal `send-keys`, separate Enter, never at a dialog,
never while the agent is busy or its release lease is held) — the same line the session cron sent,
so a working tick runs exactly as before. An empty check costs 0 LLM tokens, at most 3 HTTP calls and
well under 5 s; it still writes `data/state/tick-gate.json`, so the schedule signal and the central
fleet check see an idle agent as alive and a stuck timer or failing precheck as red (`tick`).

Presets (`tick_gate.preset`): `rendszeres` (recommended: 30 min, hourly after 3 h without work),
`mersekelt` (hourly, every 3 h after 3 h without work), `reggel-este` (two fixed checks a day,
default 08:07 and 18:07). The built-in release precheck (`check: "builtin:release"`) reads the
agent's own managed-repo list (`release.repos_file`, or `release.repos`) and its release state
read-only, makes one GitHub search for open non-draft `release:queue` PRs, reads the agent's todo
`/changes` with its own cursor (no ack), and knows the daily round (`daily_at`). Dry run:
`fleet precheck release --agent <agent>`; state: `fleet tick-gate status <agent>`. Desktop: no
timer — the session-start hook and a manual wake are the documented path.

**Waking a release agent (developer agents).** If a PR needs the owner's 👍 or an urgent merge and
the release agent is probably asleep (its next check is far), go through the backlog first: create a
todo task assigned to the release agent's principal ("PR #N: gate/merge" + link), and for a human
approval one assigned to the human. The release agent watches its own ball by default (bridge
todo-wake within about a minute, and the tick gate's todo check). `fleet wake <agent> --reason "…"
--pr <url>` does this with the existing todo client and checks the principal and the bridge. Only if
that does not work (no todo instance, no principal, bridge not running — `fleet wake` exits 3 and
prints the text) fall back to a peer message (`/rc`).

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
