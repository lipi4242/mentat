# Subagent History Template (EN)

The log that makes a persona improve.

## When to write

**After every use.** Not optional: without it the inventory is a prompt
collection, not a learning system.

**Who writes it:** by default whoever called the persona — the subagent may die
before it writes. If the persona summarised its own operation, paste that in and
add what only the caller saw (did the advice hold up?).

## Frontmatter

```yaml
---
type: subagent-history
name: <same slug as the persona>
tags: [...]
---
```

## Body structure

One dated section per use, newest first:

```markdown
## YYYY-MM-DD — <the task in one sentence>

| | |
|---|---|
| **Called by** | |
| **For what** | |
| **What it gave** | |
| **What came of it** | accepted / modified / rejected — and why |
| **Did it hold up?** | (filled in later, once known) |

**Lesson:** what we would ask differently next time, or what is worth writing
into `persona.md`.
```

## Filename

`brain/subagents/<name>/history.md`

## Why the "what came of it" column matters

A history of what the persona *said* is a transcript. A history of what
**happened to its advice** is knowledge. The rejected suggestions are often the
most instructive entries — record why.
