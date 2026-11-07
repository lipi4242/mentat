# Procedure Template (EN)

A playbook for a recurring task.

## When to create one

A task the USER wants done in a specific way more than once. Examples: "morning
email triage", "Inglor Foods order", "weekly review". If the task only happens once,
use a `todo` instead.

## Frontmatter

```yaml
---
type: procedure
name: <short-slug>
frequency: on-demand   # on-demand | daily | weekly | monthly | ...
uses_connectors: []    # list of connector names, e.g. [gmail, ticktick]
tags: [...]
---
```

## Body structure

1. **What this does** — one line: what the procedure produces or achieves.
2. **Trigger** — when to run (schedule, event, or explicit request from the USER).
3. **Steps** — numbered list in plain prose; each step is one clear action.
4. **Output** — what the USER receives at the end (report, message, updated file).
5. **Edge cases / when to ask the USER** — situations where the procedure should
   pause and check in rather than act.

## Filename

`brain/procedures/<name>.md`

## Example

```yaml
---
type: procedure
name: morning-email-triage
frequency: daily
uses_connectors: [gmail]
tags: [email, morning]
---
```

**What this does:** Summarizes overnight email and flags items needing action today.

**Trigger:** The USER says "morning check-in" or it's before 10:00 on a workday.

**Steps:**
1. Fetch unread threads from the last 12 hours via gmail connector.
2. Categorise each: action-needed / FYI / newsletter / other.
3. Draft a bullet summary grouped by category.
4. Present to the USER; await instruction.

**Output:** Bullet summary in chat; no emails sent without explicit approval.

**Edge cases:** If > 30 unread threads, ask the USER before processing all.
