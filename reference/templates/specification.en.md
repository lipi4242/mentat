# Specification Template (EN)

A build or upgrade with multiple sub-tasks under one intent.

## When to create one

Any upgrade to the agent itself OR a substantive build for the USER that has
multiple sub-tasks. If it only needs one action, use a `todo` instead.

## Frontmatter

```yaml
---
type: specification
title: <short descriptive title>
status: draft   # draft | active | done | abandoned
created: YYYY-MM-DD
target: YYYY-MM-DD   # or "ongoing"
tags: [...]
---
```

## Body structure

1. **Purpose** — one paragraph explaining why this exists and what problem it solves.
2. **Approach** — key decisions already made (bullet list).
3. **Out of scope** — explicit list of what this spec does NOT cover.
4. **Todos** — nested checkbox list; promote to a separate `todo` entity only if a
   sub-task needs independent ownership or tracking across sessions.

## Filename

`brain/specs/<slug>.md`

## Example

```yaml
---
type: specification
title: Connector: Gmail read access
status: active
created: 2026-04-29
target: 2026-05-10
tags: [connector, gmail]
---
```

**Purpose:** Give the agent read access to the USER's Gmail so it can triage
incoming email during morning check-in.

**Approach:**
- Use OAuth2 service-account with domain-wide delegation
- Credentials stored in `.env`, never committed

**Out of scope:** Sending email (separate spec), calendar integration.

## Todos

- [ ] Draft the schema
  - [ ] Frontmatter fields
  - [ ] Section structure
- [ ] Wire up validation
- [ ] Pilot on one real use
