---
name: status
description: Say which Mentat building blocks this agent has (brain, engine, fleet, admin) and which of their synergies are live — read from mentat.json and .mentat/local.json.
---

# Skill — `status`

**Invoke when** the USER asks what is installed or connected, after installing
or removing a building block, or when something that should work together
(e.g. cases in the admin) does not.

Read-only: this skill never writes either file.

## Step 1 — Run the reference tool

If `.mentat/bin/mentat_cli.py` is missing, fetch it (it is not committed):

```bash
mkdir -p .mentat/bin
for f in mentat_manifest.py mentat_rules.py mentat_roles.py mentat_cli.py; do curl -fsSL https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/reference/manifest/$f -o .mentat/bin/$f; done
```

Then, from the repo root:

```bash
python3 .mentat/bin/mentat_cli.py status
```

Exit code 0 = clean, 1 = errors, 2 = **diagnostics only** (a newer schema or an
unreadable file — nothing may act on the manifest until it is fixed or the
tool is upgraded).

## Step 2 — Without python3

Read `mentat.json` and `.mentat/local.json` yourself and apply
`reference/mentat-json.md`: an element is **present** if it is listed under
`components`, installed here (`installed.<element>`; for the admin:
`admin.url`), and its entry is valid (paths relative and inside the repo, no
endpoint in `mentat.json`, no IP address). A synergy is live when both of its
elements are present; brain + admin also needs `cases.backend: admin`.

## Step 3 — Tell the USER

Top-down, plain words, no JSON:

1. **What this agent has** — one line per building block: present / declared
   but not installed here / not installed / admin not connected. For the
   latter the tool names the admin as Mentat's todo + backlog (todos, cases,
   backlog items) — pass that on, never start an admin by hand.
2. **What works together** — only the live synergies, one line each, in the
   USER's terms ("the engine reads your cases every morning").
3. **What is wrong**, if anything — each error with the one action that fixes
   it. `cases_backend_unavailable` means case work is stopped until the
   admin is reachable again: say so, and do not fall back to markdown.

Do not suggest installing missing blocks unless the USER asks what they would add.
