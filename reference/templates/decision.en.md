# Decision Template (EN)

A choice the USER has made, kept where it can be found again — not buried in
the todo or brain dump it came up in.

## When to create one

The USER settles something that later work should follow: "we'll pay the gas
bill by transfer, not direct debit", "no new clients until March", "the site
stays in Hungarian only". Create it **in the same turn** the decision is made,
even if it came up inside a todo, a brain dump or a side remark. The todo that
carries it out links here; it does not hold the decision itself.

Not every preference is a decision. The test: would quietly doing the opposite
next month be a mistake the USER would want to be stopped from?

A decision about a **persona** (their authority, their remit) goes to
`subagent-decision` instead.

## Frontmatter

```yaml
---
type: decision
date: YYYY-MM-DD         # when it was decided
status: decided          # decided | superseded
supersedes: <filename>   # optional — the earlier decision this replaces
weight: normal           # normal | high — high = the USER said it matters
tags: [...]
---
```

## Body structure

1. **Decision** — one or two sentences, in the USER's words where possible.
2. **Why** — the reason the USER gave. This is what you quote back when they
   drift from it.
3. **Alternatives rejected** — optional, one line each.
4. **What would reopen it** — optional: the condition under which the USER said
   they would decide differently.
5. **Links** — the todos, specs, people or brain dump this came from or affects.

## Drift rule

Before you act on, plan or write something that contradicts a `decided`
decision, stop and say so: *"You decided <X> on <date>, because <why>. Do you
want to overwrite it?"* If the USER overwrites it, create a new decision with
`supersedes:` pointing at the old one, and set the old one to
`status: superseded`. **Never delete or silently edit** a decision.

## Filename

`brain/decisions/YYYY-MM-DD-<slug>.md`

## Example

```markdown
---
type: decision
date: 2026-10-14
status: decided
weight: high
tags: [household, finance]
---

**Decision:** The gas bill is paid by bank transfer each month, not by direct debit.

**Why:** "I want to see the amount before it leaves the account — last winter's estimate was off by double."

**What would reopen it:** the supplier switches to metered monthly billing.

**Links:** `brain/todos/pay-october-gas-bill.md`, `brain/brain-dumps/2026-10-14-household.md`
```
