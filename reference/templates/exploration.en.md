# Exploration Template (EN)

A living document for a topic that will be discussed multiple times before a decision.

## When to create one

A topic the USER will discuss multiple times before deciding whether it becomes a
real project. More structure than a brain dump, less commitment than a project.

## Frontmatter

```yaml
---
type: exploration
status: active   # active | paused | graduated | abandoned
created: YYYY-MM-DD
last_touched: YYYY-MM-DD
tags: [...]
---
```

## Body structure

1. **Question we're exploring** — one sentence stating what we're trying to figure out.
2. **Why now** — one short paragraph on what prompted this.
3. **Open threads** — bullet list, append-only; each item is an unanswered question or
   avenue worth investigating.
4. **Decisions taken so far** — bullet list with date prefix, e.g. `2026-04-29 — chose X
   over Y because …`.
5. **Linked brain dumps** — paths to related brain-dump files.

## Filename

`brain/explorations/<slug>.md`

## Example

```yaml
---
type: exploration
status: active
created: 2026-04-29
last_touched: 2026-04-29
tags: [product, pricing]
---
```

**Question we're exploring:** Should we charge per seat or per usage?

**Why now:** Two enterprise leads this week asked about pricing and we had no answer.

**Open threads:**
- What do direct competitors charge?
- What does the USER's gut say about positioning?

**Decisions taken so far:**
- 2026-04-30 — ruled out freemium; too costly to support.

**Linked brain dumps:** `brain/brain-dumps/2026-04-29-pricing-thoughts.md`
