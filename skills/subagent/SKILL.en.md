---
name: subagent
description: Create a persona, call it, work with it, and log the session — the full lifecycle of a reusable subagent.
---

# Skill — `subagent`

**Invoke when** you need someone who is not you: an expert, someone who knows
the business, an accountable owner, or a customer looking from outside.

Runs standalone, and is called as a subskill by `develop`.

---

## Step 0 — Read the layer

Fetch `reference/subagents.<lang>.md` if you have not this session. Personas
have a defined brain structure — do not invent it.

---

## Step 1 — Look before you build

**Read `brain/subagents/_meta.md`.** If a suitable persona exists, **use it** —
do not write a new one. A persona that gets called repeatedly is the point.

If one exists: read its `persona.md` **and the last few entries of its
`history.md`**. The history tells you what to expect and what not to ask again.
Then skip to step 3.

---

## Step 2 — Create the persona (only if none fits)

Fetch and follow these templates. Do not improvise the structure:

| File | Template |
|---|---|
| `persona.md` | `reference/templates/subagent.<lang>.md` |
| `history.md` | `reference/templates/subagent-history.<lang>.md` |
| `personal-history.md` | `reference/templates/subagent-personal-history.<lang>.md` |
| `decisions/` | `reference/templates/subagent-decision.<lang>.md` |

Two parts decide whether the persona is worth anything:

- **Authority** — what it *decides*, versus what it carries to the USER. A
  persona with no authority is a slower way of asking yourself.
- **Personal history** — where it came from. May be fabricated; that is how a
  personality is formed. For a **customer persona this is the customer
  journey**, and it is what makes the feedback relevant rather than generic.
  **Mark what is invented and what is real.**

Then **add it to `brain/subagents/_meta.md`**. A persona missing from the
inventory will not be found by the next person.

---

## Step 3 — Call it

- Put the **persona's substance** in the brief, and the task-specific part
  beside it. The persona does not change per task — the task does.
- **Give it what it must know** (the files listed in its `persona.md`). A
  persona handed a task without constraints decides by its own taste.
- **Ask for a defined answer shape.** Without one it writes an essay. State the
  numbered sections you want back.
- **Write access only if it must produce artifacts.** A reviewer measures and
  judges; it should not also implement.

### Communicating during the work

The persona is a **counterpart, not a vending machine**:

- If it goes quiet without reporting, **ask it directly** what happened — done,
  stuck, or unclear. Do not assume it finished.
- If it contradicts the USER's earlier decision and it is within its authority,
  that is allowed — but it must **write down** what the earlier decision was,
  what it decided instead, and on what basis.
- If it contradicts the USER **outside** its authority, do not swallow it: put
  both positions in front of the USER and let them decide.
- **Verify claims that matter.** A persona reporting "done" is a report, not
  evidence — the same rule as for any other work.

---

## Step 4 — Log the session. Not optional.

Append to `history.md`: what it was asked, what it gave, **what came of it**
(accepted / modified / rejected — and why), and the lesson.

**Who writes it:** whoever called it — the subagent may die before it writes. If
the persona summarised its own operation, paste that in and add what only you
saw: did the advice hold up?

> Without this the inventory is a prompt collection, not a learning system.

**If a decision record was born** while this persona was involved, and it says
something about *who they are* — copy it into `decisions/`. Not every project
ADR; only those that shape the persona.

---

## Step 5 — Upgrade when the history says so

If the history shows the persona reliably stumbling on something, or reliably
bringing something valuable, **write it into `persona.md`** and note in the
history when and why it changed.

A persona is a **versioned creature**, not a constant.
