# Acceptance Form Template (EN)

Belongs to step 4 of `development-process.md`: this is the evidence that the
work is done.

> **How to use it (caller side):** copy it next to the task
> (e.g. `<workspace>/form-<task>.md`), fill in the header and the acceptance
> criteria, then hand it to the agent with the instruction that **filling it in
> is part of the task**. An empty form means not done.
>
> **How to use it (agent side):** read it FIRST, before planning. Your plan is
> measured against it: if it doesn't cover a criterion, that should surface now,
> not at the end. Once filled, the form goes back for human review.

---

## Header

| | |
|---|---|
| **Task** | *(one sentence: the goal)* |
| **Issued by / when** | |
| **Branch** | |
| **Worktree** | |
| **Development mode** | |
| **Brainstorming questions went to** | *(autonomous / USER / external expert)* |
| **Spec rounds** | |

---

## 1. Acceptance criteria

> One row per criterion. **Every criterion needs a test.** The "what it proved"
> column is the point: not that the test is green, but **what would have
> happened if it were broken**.

| # | Criterion | Met? | Test name | What it tests | What it proved |
|---|-----------|------|-----------|---------------|----------------|
| 1 | | ☐ | | | |
| 2 | | ☐ | | | |

### Can it fail? — negative control

> **A checker that cannot fail is worse than none.** Deliberately break what the
> test guards, run it, confirm it fails. Then restore, and **prove it restored**.

| Test | How you broke it | Failed? | Restored? |
|------|------------------|---------|-----------|
| | | ☐ | ☐ |

---

## 2. Coverage — what "the whole surface" means

> Not optional. If a row doesn't apply, write **why** — blank is not an answer.

| Dimension | OK? | Evidence |
|---|---|---|
| Desktop | ☐ | |
| **Mobile** (390×844 or similar) | ☐ | |
| Tablet / mid-size | ☐ | |
| **Light mode** | ☐ | |
| **Dark mode** | ☐ | |
| Keyboard (focus, order) | ☐ | |
| Screen reader (labels, errors, aria) | ☐ | |
| Empty state | ☐ | |
| Error state | ☐ | |
| Every affected screen | ☐ | |

---

## 2.5 Trace of the question filter

> If an expert persona triaged the developer's questions: **what it kept and
> what it took to the USER.** This is what makes it auditable why the USER got
> exactly those few questions.

| Developer's question | Whose | If the expert's: what was decided, on what basis |
|---|---|---|
| | ☐ expert · ☐ USER | |

---

## 3. What I decided myself

> Every large task leaves open points. Deciding is not the problem — deciding
> **silently** is.

| The open question | What I decided | On what basis |
|---|---|---|
| | | |

---

## 4. What I did NOT do

> Dropped dimension, deferred part, known limitation. **A stated gap is
> manageable; an unstated one is a surprise.**

| What was left out | Why | Risk |
|---|---|---|
| | | |

---

## 5. Reviewer rounds

> Every round goes here, so the process is auditable both ways: what was said,
> what came of it, and if nothing did, why.

### Round 1 — *(reviewer kind)*

| What they said | What came of it | If rejected: why |
|---|---|---|
| | | |

---

## 6. State of the measurement

> **The state of the measuring instrument is part of the measurement.**

| Question | Answer |
|---|---|
| Measured in a clean `git worktree`? *(not the working tree)* | ☐ |
| Fresh dependency install (`npm ci` or equivalent)? | ☐ |
| Working tree clean after measuring? | ☐ |
| Any untracked file the build would fail without? | |
| Did dependencies change (manifest / lockfile)? | |

---

## 7. Summary

| | |
|---|---|
| **Done?** | ☐ yes · ☐ yes, with reservations · ☐ no |
| **If with reservations: what?** | |
| **Commits** | |
| **Tests total** | |
| **Typecheck / lint** | ☐ clean |
| **What should a human look at first?** | *(where to click, what to open)* |
