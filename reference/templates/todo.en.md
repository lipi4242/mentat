# Todo Template (EN)

A single concrete task with a doable shape.

## When to create one

Any concrete task with a doable shape — verb + object, can be marked done.
If a task has more than ~5 sub-steps or spans multiple sessions, consider a
`specification` instead.

## Frontmatter

```yaml
---
type: todo
status: open   # open | in-progress | done | cancelled
priority: med  # low | med | high
due: YYYY-MM-DD   # optional
tags: [...]
---
```

## Body structure

1. **Task** — one line, verb-first (e.g. "Draft invoice for April").
2. **Context** — why this matters and where it came from (1–3 sentences or link).
3. **Definition of done** — 1–3 bullets stating exactly when this can be marked done.

## Filename

`brain/todos/<slug>.md`

## Example

```yaml
---
type: todo
status: open
priority: high
due: 2026-05-02
tags: [finance, acme]
---
```

**Task:** Draft April invoice for Acme Studio client.

**Context:** Monthly billing cycle. Template lives at `brain/procedures/invoicing.md`.

**Definition of done:**
- Invoice PDF generated with correct line items
- Sent to client via email
- Payment date noted in finance tracker
