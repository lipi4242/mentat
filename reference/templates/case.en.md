# Case Template (EN)

Something the USER has to get done and keep track of over time — once, or
again and again: the gas bill due on the 10th of every month, the tax return
due on 20 May, an insurance claim waiting for the insurer.

## When to create one (proposal — adjust with the USER, record it in `brain/cases/_meta.md`)

A case is something that

1. **has a done state** — or, if it recurs, each occurrence can be done;
2. **has a next step** (even if it is "wait for X");
3. **has a date**: a deadline, or when to look at it again.

Not a case: a **project** or **exploration** (a direction, no "done"), a
**plain todo** (one step, no context — keep it a todo), a **decision** (a rule
to respect, not something to get done), an **area of life** (finances,
health: a place where cases gather). Borderline: a todo that has been rolling
for weeks and depends on someone else → make it a case.

## Frontmatter

The field names are the same as the admin's cases plugin, so moving a case
there is a field-by-field copy, not a guess from prose.

```yaml
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RS   # ULID, generated once, never changed
title: Gas bill
status: open            # open | waiting | done | dropped
description: The monthly gas bill, paid by transfer   # one or two sentences: what it is about
next_action: Pay by transfer once the bill arrives   # one sentence; when waiting: "wait for X"
due_at: 2026-11-10      # one-off: the deadline; recurring: the earliest open occurrence
recurrence: monthly:10  # monthly:<day> | quarterly:<day> | yearly:<MM-DD> | weekly:<mon..sun> | empty
anchor_at: 2026-10-10   # recurring: the first due date of the series (required)
occurrences:            # recurring: closed occurrences only, oldest first
  - { due_at: 2026-10-10, status: done, done_at: 2026-10-08, note: paid by transfer }
extra: {}               # your own fields (a category, an amount), until they prove useful
tags: [...]
---
```

A one-off case has no `recurrence`, `anchor_at` or `occurrences`: `due_at`
is the deadline itself (see the second example).

When the USER keeps needing a field that is not here (a category, an
amount, a priority): in markdown mode put it in `extra`. With an admin it
becomes an own field in the admin (the admin's `agent/EXTENDING.md`), and
the `cases` CLI writes it with `--set field=value`.

Generate the ULID once, when you create the file (Python 3):

```bash
python3 -c "import os,time;n=(int(time.time()*1000)<<80)|int.from_bytes(os.urandom(10),'big');a='0123456789ABCDEFGHJKMNPQRSTVWXYZ';print(''.join(a[(n>>5*i)&31] for i in range(25,-1,-1)))"
```

## Body structure

1. **Context** — history, the calculation, documents, people involved (link
   them). This part always stays in markdown, even after a move to the admin.
2. **Log** — dated lines of what happened.

## Closing a due date

- **One-off case:** set `status: done` (or `dropped`), and log why.
- **Recurring case:** close **only the earliest open occurrence** — the one in
  `due_at`. Append it to `occurrences` (`status: done` or `skipped`, `done_at`,
  `note`), then move `due_at` to the next date of the series: the next
  `anchor_at` + n × `recurrence` that is not closed yet. If the day does not
  exist in a month (31st), use the month's last day. `quarterly:<day>` (a
  quarterly VAT return, say) steps three months from the month of
  `anchor_at`: `quarterly:20` from 2026-01-20 → 20 January, April, July,
  October; `quarterly:31` anchored in November falls on 28 February. An unpaid October never
  disappears behind a paid November: if two months are overdue, both are
  open and October is closed first. The case itself stays `open`.
- **A first month off the rule:** when the first due date misses the rule (by
  the 10th from now on, but October's 10th has passed, so October is due on the
  20th), it is still part of the series, not a separate one-off case:
  `anchor_at: 2026-10-10`, `due_at: 2026-10-20` (the earliest open occurrence's
  `due_at` may move later within its own month). Closing it writes the series
  date (2026-10-10) into `occurrences`. With the `cases` CLI:
  `add --recurrence monthly:10 --due 2026-10-20`.
- Never close a date the USER has not confirmed as done.

## Where it lives

`brain/cases/<slug>.md`. `mentat.json` says where cases are tracked:
`cases.backend: markdown` (the default) — the frontmatter above is the record.
With `cases.backend: admin` the tracked fields live only in the admin and this
file keeps `case_id` plus the context; the admin's `brain_ref` points back to
this file. Moving between the two is done with `cases migrate`, never by hand.

## Example

```markdown
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RS
title: Gas bill
description: The monthly gas bill, due on the 10th, paid by transfer
status: open
next_action: Pay by transfer once the bill arrives
due_at: 2026-11-10
recurrence: monthly:10
anchor_at: 2026-10-10
occurrences:
  - { due_at: 2026-10-10, status: done, done_at: 2026-10-08, note: paid by transfer }
tags: [household, finance]
---

**Context:** Paid by transfer, not direct debit — see `brain/decisions/2026-10-14-gas-by-transfer.md`.

**Log:**
- 2026-10-08 — October paid.
```

A one-off case:

```markdown
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RT
title: Tax return 2026
description: The yearly income tax return, from the tax office's draft
status: open
next_action: Check the draft, add the rental income
due_at: 2027-05-20
tags: [finance]
---

**Context:** The draft misses the rental income; the lease: `brain/documents/lease.md`.

**Log:**
- 2027-03-18 — the draft arrived.
```

## Before a date or status change

Before you change a case's `due_at`, its `status` or one of its occurrences, read the case's
`description`, `next_action`, the `occurrences` notes and its body. If any of them sets a
condition ("not before …", "only after X", "waiting for Y") and the requested change conflicts
with it, quote the condition, ask, and write only after the answer. Without a conflict, no question.
