# Brain Dump Template (EN)

A raw record of a long message from the USER. Captured verbatim before processing.

## When to create one

The USER sends a message ≥ ~200 words that's a thought stream — multiple ideas,
requirements, or context dumped together. You recognize it as more than a simple
instruction.

## Frontmatter

```yaml
---
type: brain-dump
date: YYYY-MM-DD
topic: <2-4 word slug>
processed: false
tags: [...]
---
```

## Body structure

1. **Raw transcript** — paste the USER's message verbatim. Do not edit, summarize,
   or reflow.
2. **(After processing)** A "Processed" section listing the entities extracted, links
   to the entity files created/updated, and a one-paragraph synthesis.
3. **Open questions** — only if any (no empty header); what you could not settle from the text, one line each,
   marked `- [ ] to clarify: ...`.

## Keeping it current

When the USER later answers one of the open questions — in this session or a
later one — come back to this file in the same turn: tick it
(`- [x] clarified YYYY-MM-DD: <answer in one line> → <file where it landed>`).
The raw transcript itself is never edited.

## Filename

`brain/brain-dumps/YYYY-MM-DD-<topic-slug>.md`

## Example

```markdown
---
type: brain-dump
date: 2026-04-29
topic: q3-strategy
processed: false
tags: [strategy, work]
---

# Q3 Strategy Brain Dump

So I've been thinking about Q3 and there are three things on my mind...
[verbatim continues]
```
