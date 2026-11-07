# Changelog

Every release also ships a machine-readable `release.json` at the root of its
tag.

## 0.4.1

A patch release for problems found while upgrading two live agents to 0.4.0. Not breaking.

- **The secrets gate no longer mistakes a search pattern for a key file**: `grep`, `rg` and `ag`
  patterns are text, so `grep -o '"lease_token": …' out.json` is allowed again. File arguments and
  `grep -f <file>` are still checked, and key files stay blocked. Plugin 1.5.1.
- **`fleet secrets hook status` tells the truth**: it reports a gate that was never installed as
  missing and exits non-zero, instead of showing green.
- **One fleet plugin, installed for one agent**: `fleet upgrade` switches the old `fleet@fleet-ops`
  plugin off, so two "fleet" plugins never run side by side. `fleet plugin install <agent>`
  installs the plugin with local scope in that agent's repo, so other agents sharing the box's
  Claude account are not affected; `fleet setup` does the same.
- **Releases check the install line**: a README `git clone --branch` pin that does not match the
  release stops the release.

## 0.4.0

Released together with the Mentat brain 0.4.0 and anytime-engine 0.4.0.
Not breaking.

- **Secrets without their values**: `fleet secrets scan` lists an agent's secret files by name,
  place, format and key name, never by value. `approve` records an itemised owner approval that
  lasts at most 60 minutes and works once per item. `move` and `copy` relocate one key without the
  value showing up in arguments or output. `audit` reports, by file and line, where a listed value
  leaked into a transcript, a repo or its git history. <!-- cap: fleet-secrets -->
- **The secrets gate**: a deny-only hook in the fleet plugin (1.5.0) that `fleet secrets hook
  install` also puts into every Claude config on the box. It keeps key files, another agent's
  transcript and environment dumps out of the conversation, also when they are reached through
  shell tools. It tests itself before it switches on, and stays off if the test fails.
  <!-- cap: fleet-secrets-gate -->
- **A boundary between agents**: the same hook always blocks hand-writing a systemd unit, the fleet
  registry or another agent's rule files on its main branch. While a merge is in progress
  (`fleet secrets merge-mode`, at most 7 days) it also blocks git writes to another agent's main
  branch, typing into a tmux pane, and running another agent's code against live services. It
  slows a careless agent down; it is not a sandbox. <!-- cap: fleet-agent-boundary -->
- **Retire, merge or upgrade an agent step by step**: `fleet plan-merge --donor <old> --recipient
  <new>` prints the order with measured state and two STOP points where the owner decides, and the
  `/fleet:merge-agents` skill walks through it. `fleet retire` stops an agent reversibly; nothing
  is deleted. `fleet --help`, the fleet rule and every install point to the procedure.
  <!-- cap: fleet-merge-agents -->
- **Hold an agent's outward actions**: while `fleet hold-outward` is set, every tick of that agent
  is a dry run, so it can be rebuilt next to its live copy without anything going out;
  `fleet release-outward` lifts it. Needs anytime-engine 0.4.0. <!-- cap: fleet-outward-hold -->
- **Reach an agent on any box**: `fleet probe` reports over ssh whether the agent's login is alive,
  which model it really runs, and how far the box's fleet code and registry are behind. `fleet
  login` runs the Claude login on a remote box and takes the code on stdin, never in arguments or
  logs. `fleet ask` leaves a question file for an agent and waits for its answer, without Telegram
  or Remote Control. <!-- cap: fleet-remote-ops -->
- **Registry changes without editing JSON**: `fleet registry set <agent> status=…` or
  `tick_period_s=…` changes one field with the owner's yes and rewrites the tick timer to match.
  A `boxes.json` written as a plain list is now read too, so `roster`, `doctor` and `ask` no longer
  stop on it. <!-- cap: fleet-registry-set -->

## 0.3.1

Released together with the Mentat brain 0.3.1 and anytime-engine 0.3.1.

- **The identity gate as a plugin hook**: every agent on the box gets the same check before your
  e-mail address leaves for a third party: asked in an interactive session, denied headless.
  <!-- cap: fleet-identity-gate -->
- **doctor checks every agent's guard**: `fleet doctor` shows red when an agent's guard or its
  Claude Code version is not up to date with 0.3.1. Nothing is rewritten. <!-- cap: doctor-guard-check -->
- **New agents come up cleanly**: `fleet validate` also finds a runbook relative to the
  registry repo's root; the session-id hook reads `FLEET_AGENT` and the older `THUFIR_AGENT`, and
  `seed_settings` replaces an older hook entry instead of adding a second one.
  <!-- cap: fleet-setup-fixes -->
- **Safer defaults on the server**: fewer elevated rights on the box, and no menu questions for an
  agent that runs unattended. <!-- cap: fleet-hardening -->
- **The capability tree across the fleet**: `fleet capabilities collect` gathers each agent's
  exported capabilities on this box (filtered, outside the repos); `fleet capabilities find --as
  <agent>` searches them with the right visibility. <!-- cap: fleet-capabilities -->

## 0.3.0

First public release of the fleet runner for always-on agents.

- **Setup in one command** - `fleet setup` provisions a box and an agent end to
  end; `fleet init` writes the registry entry from a repository, `fleet wait-up`
  blocks until an agent reports healthy.
- **One controller** - `fleet reconcile` (5-minute timer) enforces the desired
  state: OOM protection, tick re-arm, duplicate alerts. `reconcile-fast`
  brings a dead agent process back in about a minute. Installs are
  transactional and finish on a green postcheck.
- **Bridge 2.0.1** - Telegram-to-tmux bridge with webhook output, delivery
  receipts, chunked output, a token lock and strict argument parsing.
- **Drift and rollback** - `fleet bridge status` reports sha256 drift of the
  installed bridge; `fleet bridge rollback` restores the previous one.
- **mentat.json synergies** - `fleet join` / `upgrade` read the Mentat
  manifest and warn when the brain is not loaded by `CLAUDE.md`.
- **Claude plugin** - skills `roster`, `doctor`, `new-agent`, `runtime` and a
  SessionStart hook (plugin version 1.2.0).
- **Templates** - systemd units and timers, rule file, a separate
  `claude-auth.env` for the agent's Claude token.
