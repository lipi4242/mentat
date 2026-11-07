# Subagent Decision Record Template (EN)

An ADR kept **at the persona**, not only in the project.

## When to create one

A decision record is born in a project while this persona was involved, and it
is one of:

- **about them** — their authority, their remit, how they are called;
- **about their relationship to the project** — what they own here, what they
  do not;
- **an answer they gave that will keep mattering** — a call that shapes who
  they are, and that a future call should not re-litigate from scratch.

If the decision is purely about the project and says nothing about this persona,
leave it in the project. **Do not copy everything** — an inventory of every ADR
is a second archive, not a personality.

## Frontmatter

```yaml
---
type: subagent-decision
name: <same slug as the persona>
number: NNN
status: decided        # decided | superseded
supersedes: NNN        # optional
tags: [...]
---
```

## Body structure

1. **Context** — what was being decided, and why it reached this persona.
2. **Decision** — what was decided, in one paragraph.
3. **Who decided** — the persona, the USER, or both. If the persona decided
   against an earlier USER decision, **say so explicitly**.
4. **Consequences** — what follows, including what this closes off.
5. **What this says about the persona** — the sentence that makes it worth
   keeping here rather than only in the project.

## Numbering

Sequential per persona, three digits, never reused: `001-`, `002-`…
A superseded record is **not deleted** — it is marked, and the new one links back.

## Filename

`brain/subagents/<name>/decisions/NNN-<slug>.md`
