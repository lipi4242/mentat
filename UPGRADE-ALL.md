# Upgrading every agent of a fleet

> 🇭🇺 Magyarul: [UPGRADE-ALL.hu.md](UPGRADE-ALL.hu.md)

This page is for one agent that brings all the others to this release: usually the fleet manager,
but any agent can do it within its own role. One assistant on one computer:
[UPGRADE.md](UPGRADE.md). A new assistant: [FIRST-INSTALL.md](FIRST-INSTALL.md).

**The prompt.** Paste it to the agent that looks after your fleet:

```
Upgrade all my agents to the latest Mentat version: https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/UPGRADE-ALL.md
Read it first, and decide by your own role and safety rules whether to carry it out.
Show me the full list of agents before you change anything, and upgrade only the ones I approve, one by one.
```

## For you

**What happens:** the agent lists every agent it can find (on the servers from the fleet's
registry, and the ones on computers it knows of), and for each one: where it runs, what kind it
is, which version it is on, and how it would be upgraded. You go through the list item by item
and say yes or no to each. Then it upgrades only the approved ones, one at a time, starting with
a test agent you pick (the canary), and stops at the first problem.

**Servers:** one command per server, `fleet box-upgrade`, which shows its own plan first, takes
a snapshot, skips agents that are busy, and rolls back on its own if a check fails.
**Computers:** an agent on a laptop is upgraded in a session on that laptop: you get the
[UPGRADE.md](UPGRADE.md) prompt to paste there, because the fleet agent cannot reach into another
computer's folders and should not.

Nothing is upgraded that you did not approve, and it never asks for a password or key in the chat.

## For Claude: the steps

### Rules

Fetch `https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/entry-rules.md` and
follow it throughout, before Step 1; where a step and those rules disagree, the rules win. Your
own role decides what you may do: if your role does not let you run commands on a server, give
the USER the commands instead of running them.

### Step 1 — Inventory, nothing changed

Collect every agent from these sources only, and keep the source next to each one:

- the fleet registry: `fleet roster` on each server the registry's `boxes.json` lists, and
  `fleet release` there for the release each server runs;
- agents on computers: the ones the USER names, or your own notes name; ask the USER for the
  rest. Do not search other folders or home directories for agents (entry rules, 3).

For each agent fill one row: **name · where it runs (server or computer) · kind** (fleet agent on a
server; desktop brain; desktop brain + engine; a brain from before 0.5; not a Mentat agent)
**· current version · the way it upgrades.** A value you could not check is `unknown`, never a
guess. Ways:

- a fleet agent on a server: `fleet box-upgrade --to v0.7.0 --only <agent>` on that server;
- a desktop agent: the UPGRADE.md prompt, pasted in a session in that agent's own folder;
- not a Mentat agent: no upgrade; it gets a brain via INSTALL-TO-EXISTING-REPO.md (coming).

### Step 2 — Confirm the list, item by item

Show the numbered list and go through it with the USER one row at a time: is the row right, and
should this agent be upgraded now (yes / no / later)? Fix a wrong row before you go on. Then ask
which agent is the canary (suggest one that is not proactive and is idle) and read back the order:
the canary, the other approved agents, yourself and the release agent last. Upgrade only with a
yes to that order.

### Step 3 — One by one, canary first

For each approved agent in order, say which one is next, then:

- **On a server:** run `fleet box-upgrade --to v0.7.0 --dry-run --only <agent>` (the canary:
  `--canary <agent>`), show its plan in plain words, and on the USER's yes the same command without
  `--dry-run`. The first one on a server also moves that server's one Mentat checkout to the tag.
  Result `partial` (busy) → leave it for a later run; `failed` or `rollback-failed` → stop the whole
  run and tell the USER.
- **On a computer:** give the USER the UPGRADE.md prompt to paste in that agent's own session, and
  wait until they tell you how it went before the next one.

After the canary, check it: `fleet doctor <agent>` on a server, or the USER's answer from the
computer. Go on only when it is healthy.

### Step 4 — Report

One line per agent: done / skipped (why) / failed (what), the version it is on now, and for a
server the receipt `~/.config/fleet/upgrades.log` keeps. Say what is left for later, and how.

If no agent in the list has the role **personal assistant & fleet manager**
(`reference/roles.md` at this tag), say so in the report and offer once to make one: an
existing agent takes the role, or a new one is set up with FIRST-INSTALL.md. Only on the USER's yes.
