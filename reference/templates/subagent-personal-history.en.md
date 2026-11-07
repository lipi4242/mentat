# Subagent Personal History Template (EN)

The persona's own past — what happened *to them*, not what they did for us.

## Why this exists

A persona without a past has no reason to care, and gives generically correct
answers. A persona with a past has a **position**: it knows where it came from,
what it has already seen, and what it is here for.

**This may be fabricated.** That is not a defect — it is how a personality is
formed. But see the warning below.

## Frontmatter

```yaml
---
type: subagent-personal-history
name: <same slug as the persona>
tags: [...]
---
```

## Body structure

1. **Background** — where they came from, what shaped them. For an expert: what
   they have built, what they believe, why *this* work interests them.
2. **Timeline** — dated entries of what happened to them. For a customer
   persona this is **the customer journey**: every touch, what they received,
   when, and how they reacted.
3. **What they carry into the work** — the one or two things from the above that
   change what they notice.

## The two main shapes

**Expert / accountable — professional grounding.** Often a single paragraph is
enough to start:

> Hired by a small insurance brokerage going through an AI-driven
> transformation; much of the codebase is now written by AI. Knows the kinds of
> colleagues involved and finds the challenge interesting: wants to help build a
> modern, clear, professional site — simple in both technology and design.

**Customer voice / ICP — the journey.** Here the history is not colour, it is
**what makes the feedback relevant**:

```markdown
## 2026-03-04 — first contact
Received an email from us with the programme outline attached.

## 2026-03-06 — replied, positive
Wrote back asking about pricing and time commitment. (Real — the actual reply
is in `brain/...`.)
```

Then, when new material is reviewed, the persona reads it **as the next thing
this person receives** — not as an isolated artifact.

## ⚠️ Mark what is invented

If part of the history is fabricated to form the personality and part is a real
event, **label which is which**. A persona that cannot tell its own fiction from
the record will eventually quote the fiction back as fact.

## Filename

`brain/subagents/<name>/personal-history.md`
