# Subagents — the fifth layer

> **New in this release.** The brain had four layers: entities, connectors,
> procedures, projects. This adds a fifth: **subagents** — reusable personas
> with their own brain and their own history.

## What this is

A subagent is not a prompt. It is a **role**: someone with expertise, authority,
and a track record.

When you spawn a helper for a task, the brief you wrote dies with the session.
Next time, someone rewrites it — worse, because they don't remember what worked
and what didn't. The subagent layer fixes that: **the persona persists, and
gets better every time you use it.**

## Why it matters

Three things become possible that were not before:

1. **Reuse.** A well-built persona is an asset, not a throwaway. Call it again.
2. **Learning.** Every use is logged. Patterns emerge: what this persona is
   reliably good at, and where it consistently misses.
3. **Delegation with authority.** A persona can be given a **domain it decides
   in** — not just an opinion it offers. That is what makes it worth more than
   asking the USER.

## The four kinds

Boundaries are permeable; the point is what the persona is *for*.

| Kind | For | Example |
|---|---|---|
| **Expert** | Master of one discipline; decides within it | UX master, database expert |
| **Business-aware** | Knows the company and market from inside | The trade, the customers, the pricing |
| **Accountable** | Owns an **area**, checks it on a schedule | Chief Cybersecurity Officer — woken daily to review the backlog, the app, and run a penetration test |
| **Customer voice** | Looks from outside, as a user, hunting for faults | A 65-year-old customer on a phone |

## Folder structure

Each persona gets its own folder. **A persona has a brain of the same shape you
do** — identity, history, decisions — because that is what lets it act as a
someone rather than a prompt.

```
brain/subagents/            (agy/subagentek/ in Hungarian mode)
  _meta.md                  ← the inventory: who exists, what for
  <persona-name>/
    persona.md              ← WHO THEY ARE: role, knowledge, authority, constraints
    history.md              ← OUR JOINT WORK: every use, dated
    personal-history.md     ← THEIR OWN STORY: where they came from, what happened to them
    decisions/              ← ADRs that matter to them
      _meta.md
      NNN-<slug>.md
```

### The four files, and what each is for

**`persona.md` — the identity.** Plays the same role for the persona that
`AGENTS.md` plays for you: who they are, what they must know, what they decide.
This is what you hand them when you call them.

**`history.md` — the story of working together.** What they helped with, how we
worked, what we decided, what came of their advice. This is the record that makes
the persona improve: patterns emerge about what they are reliably good at, and
where they consistently miss.

**`personal-history.md` — their own past.** Treat this as a real life story: what
happened *to them*, not what they did for us. **This may be fabricated** — that
is not a defect, it is how a personality is formed. A persona with a past
interprets new material differently than one without.

**`decisions/` — ADRs that concern them.** When a decision record is born in a
project while this persona was involved, **save a copy here too** — whether the
ADR is about them, about their relationship to the project, or about an
important answer they gave that will keep mattering to who they are.

Fetch the templates before creating any of them — see the templates index.

---

## Personal history — why a fabricated past is useful

This is the part that most often gets skipped, and it is the part that makes the
difference between a persona and a system prompt.

**A persona without a past has no reason to care.** It gives generically correct
answers. A persona with a past has a *position*: it knows where it came from,
what it has already seen, and what it is here for.

### Two ways it is used

**For expert and accountable personas: professional grounding.**

> *Example — UX master.* Hired by a small insurance brokerage that is going
> through an AI-driven transformation; much of the codebase is now written by AI.
> They know the kinds of colleagues involved, and find the challenge interesting:
> they would like to help build a modern, clear, professional website — simple in
> both technology and design — and applications people can actually use.

That paragraph alone is enough to start with. It tells the persona what it cares
about, which changes what it notices.

**For customer personas (ICPs): the customer journey.** Here personal history is
not colour — **it is the thing that makes the feedback relevant.**

> *Example.* The persona received an email and an attachment from us on a given
> date. That is the point of contact, and everything afterwards is read in its
> light. If it was a sales email and the persona responded positively, **the
> response goes into the history too.** Then, when we later develop the actual
> material — the program content, the next page, the follow-up — the persona
> reviews it *knowing the first email*, from inside its own journey and context.

A customer persona without a journey gives you a review from nowhere. One with a
journey tells you whether **this** message makes sense as the **next** thing
that person receives.

### Where it is relevant

| Kind | `personal-history.md` | `decisions/` |
|---|---|---|
| **Expert** | professional background: what they have built, what they believe, why this work interests them | ADRs in their domain, and the calls they made |
| **Business-aware** | how they came to know the company and the market | business and positioning decisions |
| **Accountable** | their remit: what they were made responsible for, and when | policies they set, incidents they ruled on |
| **Customer voice / ICP** | **the customer journey** — every touch, dated: what they received, when, how they reacted | what they said yes and no to, and why |

> ⚠️ **Keep fabricated and real apart.** If part of a personal history is
> invented to form the personality, and part is a real event (an actual email
> actually sent), **mark which is which**. A persona that cannot tell its own
> fiction from the record will eventually quote the fiction back as fact.

## How to use one

**Before spawning any helper, check the inventory.** Do not write a new persona
if a suitable one exists.

1. Read its `persona.md` **and the last few entries of its `history.md`**. The
   history tells you what to expect and what not to ask again.
2. Put the persona's substance in the brief; write the task-specific part
   beside it. **The persona does not change per task — the task does.**
3. **After the work, write the history entry.** This is not optional. Without
   it the inventory is a prompt collection, not a learning system.

### Who writes the history

By default, **whoever called them** — because the subagent may die before it
writes. If the persona summarises its own operation, better: the caller pastes
that in and adds what only the caller saw (did the advice hold up?).

### Upgrading a persona

When the history shows a persona reliably stumbling on something, or reliably
bringing something valuable: **write it into `persona.md`**, and note in the
history when and why it changed. A persona is a **versioned creature**, not a
constant.

## Where they plug into development

See `development-process.md`. In short:

- **step 2.3** — an expert persona acts as the **question filter**: it decides
  what is its own call and what genuinely needs the USER;
- **step 6** — customer-voice and adversarial personas review the work, in
  several rounds, and their feedback is recorded in the acceptance form.

## A caution

**A persona is not a licence to stop thinking.** It concentrates judgement; it
does not replace yours. If a persona's advice is wrong, say so — and write that
into its history, because that is exactly the entry that makes the next call
better.
