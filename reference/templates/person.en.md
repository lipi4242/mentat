# Person Template (EN)

A profile for someone whose recurring details matter.

## When to create one

The USER mentions someone twice or more, OR someone whose details affect future
decisions — the USER themselves, family members, key colleagues, key clients.

## Frontmatter

```yaml
---
type: person
name: Full Name
role: <job title or relationship>
relationship: colleague | client | friend | family | self
contact: email or handle (optional)
tags: [...]
---
```

## Body structure

1. **Who they are** — 1–3 sentences: role, context, why they appear in this workspace.
2. **Context with the USER** — relationship history, how they met, what they work on
   together.
3. **What matters** — preferences, constraints, sensitivities relevant to interactions.
4. **Recurring topics** — bullet list of subjects that come up repeatedly with this
   person.

## Filename

`brain/people/<slug>.md`

## Example

```yaml
---
type: person
name: Anna Kovács
role: Lead designer, Acme Studio
relationship: colleague
contact: anna@example.com
tags: [design, acme]
---
```

**Who they are:** Anna is the lead designer on Acme Studio. She owns the visual system
and reviews all front-end PRs.

**Context with the USER:** Working together since 2024. Prefers async over meetings.

**What matters:** Never ping on Fridays. Dislikes scope creep mid-sprint.

**Recurring topics:**
- Component library updates
- Brand consistency checks
