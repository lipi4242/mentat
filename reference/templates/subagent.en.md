# Subagent Template (EN)

A reusable persona: someone with expertise, authority, and a track record.

## When to create one

You are about to spawn a helper, and **no suitable persona exists in the
inventory** (`brain/subagents/_meta.md`). If one exists, use it — do not write
a new one.

Create a persona when the role will recur: an expert you'll consult again, a
customer voice that reviews releases, an accountable owner who checks an area
on a schedule.

## Frontmatter

```yaml
---
type: subagent
name: <short-slug>
kind: expert          # expert | business-aware | accountable | customer-voice
status: active        # active | experimental | retired
tags: [...]
---
```

## Body structure

1. **In one sentence** — who they are, and why call them instead of doing it yourself.
2. **Who they are** — role, viewpoint, posture. Not a biography: what matters is
   **where they look from**, and what they notice that others miss.
3. **What they must be given** — files they must read before working. A persona
   handed a task without constraints will decide by its own taste.
4. **Authority** — a two-column table: what they **decide**, and what they carry
   to the USER. Include the check: *"if I put this in front of the USER, could
   they answer it better than I can?"* If not — it's theirs.
5. **Constraints** — what the project already decided, and is not theirs to
   overrule.
6. **How to call them** — model (and why), tools, typical task, **what you must
   ask for** (the shape of the answer — without it they write an essay), and
   what not to ask.
7. **What their history taught** — grows from `history.md`. This is what makes
   the persona better than when it was written.

## Filename

`brain/subagents/<name>/persona.md`

## Note

Give write access only if the persona is meant to produce artifacts. An expert
reviewer measures and judges — it should not also implement.
