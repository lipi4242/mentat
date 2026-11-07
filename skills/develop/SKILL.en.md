---
name: develop
description: Run a large, under-specified piece of work end to end — mode choice, specification, personas, acceptance form, isolated worktree, reviewer rounds.
---

# Skill — `develop`

**Invoke when** the USER asks for something **large in scope** AND **not fully
specified**.

**Do not invoke** for a typo, a rename, a bounded bug fix, or a question. Do
those.

> **The test:** if the finished work could take several non-interchangeable
> correct shapes, and you cannot tell which one they want — run this skill.

---

## Step 0 — Read the process

Fetch `reference/development-process.<lang>.md`. This skill is the runnable
order; that document is the reasoning behind it. If they ever disagree, the
document wins.

---

## Step 1 — Ask which development mode. Do not start.

**One structured round.** Offer the frameworks available here plus the
alternatives that fit: direct implementation, plan only, survey only.

**Stop and wait for the answer.** Everything below depends on it.

---

## Step 2 — If a plan-driven process was chosen, ask two more things

**In the same round, not drip-fed:**

1. **How many specification rounds?** Several / one / start now. If "start now",
   you make the missing decisions — but you **write each one down** with its
   reasoning.
2. **Who answers the brainstorming questions?** Autonomous / the USER / an
   external expert model.

### Step 2.3 — The question filter (if an expert persona is on the team)

Run the `subagent` skill to bring in the expert. Then:

1. The developer writes down **everything** it would clarify. It does not
   self-censor — filtering is not its job.
2. **The expert triages each question**: *"my call"* → it decides and records the
   decision with reasoning; *"genuinely theirs"* → it goes to the short list.
3. The two together assemble **one** question round for the USER.

> The check, when hesitating: *"if I put this in front of the USER, could they
> answer it better than I can?"* If not — don't. Every unnecessary question
> spends their attention and crowds out the ones only they can answer.

---

## Step 3 — Write full-coverage acceptance criteria

Not more detailed than agreed — but covering the **whole surface**. For a user
interface, at minimum: every screen size (**including mobile**), every display
mode, keyboard and screen reader, every affected screen, error and empty states.

If you deliberately drop a dimension, **write that down and why**.

---

## Step 4 — Attach the acceptance form

Fetch `reference/templates/acceptance-form.<lang>.md`, copy it beside the task,
fill in the header and criteria, and hand it over with the instruction that
**filling it in is part of the work**.

Require per criterion: **test name · what it tests · what it proved.** And the
negative control — break what the test guards, confirm it fails, restore it,
prove the restore.

> "The test is green" is not evidence. The question is what would have happened
> if it were broken.

---

## Step 5 — Isolate the work

The developer works in its **own `git worktree`, on its own branch**. Two
reasons, both learned the hard way: concurrent agents overwrite each other, and
**the working tree lies** — it contains untracked files, so a green measurement
there may describe only your machine.

On completion: merge the branch, remove the worktree. Leave no debris.

---

## Step 6 — Reviewer rounds

Bring in personas via the `subagent` skill:

- **Customer voice** — reviews the plan *and* the finished version, over
  **several rounds**; the first finds the obvious, the second finds what broke
  while fixing the first.
- **Adversarial reviewer** — evaluates critically; its job is not to agree.

**All feedback goes into the form** — what was said, what came of it, and if
nothing did, why.

---

## Step 7 — Document in place, and log the personas

Two things are easy to skip at the end, and both cost later:

1. **Documentation goes where it belongs** — in the project's own docs, next to
   what it describes, with any index files updated. Not in the chat, not in a
   stray file.
2. **Every persona used gets a history entry** (`subagent` skill, step 4). A
   persona whose session is not logged has learned nothing.

Then run the filled form past the USER. The form is worth something precisely
because a human looks at it and says no.

---

## What this skill does not do

It does not replace your judgement; a filled form does not guarantee quality;
and merging is not shipping. If the project has a release process, follow it.
