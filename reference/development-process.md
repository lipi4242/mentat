# Development process — for large, under-specified work

> **New in this release.** A procedure for the case where the USER asks for
> something big and does not fully specify it. Pairs with `subagents.md`: the
> personas plug in at steps 2.3 and 6.

## When this applies

The work is **large in scope** AND **not fully specified**.

Not this: fixing a typo, renaming a field, answering a question, a bounded bug
fix. Just do those.

**The test, when in doubt:** if the finished work could take several
non-interchangeable correct shapes, and you cannot tell which one they want —
this procedure applies.

## Why it exists

Three expensive, real failures:

1. **An agent produced a long, careful proposal that had to be thrown away**,
   because it started in the wrong frame. The work wasn't bad — the *question*
   wasn't settled before it began.
2. **A "done" report on work that did not function.** A form told a user to
   fill in a name field that was already filled — while a thousand tests were
   green. No test suite covered that class of failure.
3. **A green measurement that described the measuring machine, not the repo.**
   Untracked files, stale dependencies, leftovers from a previous run — each
   looked exactly like completed work.

Three rules hold the whole thing up:

> **Settle the intent before anyone starts working.**
> **"Done" comes with evidence, not with a report.**
> **The state of the measuring instrument is part of the measurement.**

---

## 1. Ask which development mode

**Always ask before you start anything.** Do not guess, do not default.

Make it one structured round — do not drip-feed. Offer the frameworks available
in this project alongside the alternatives that fit the task: direct
implementation, plan only, survey only.

---

## 2. If a plan-driven process is chosen, two questions follow

Together these decide how much human time goes in, and who makes the
professional calls.

### 2.1 How much do they want to shape the specification?

Not yes/no — **how many rounds**:

- **Several rounds** — play N question rounds until a detailed spec exists. One
  topic per round; do not scatter.
- **One round** — ask once, then go.
- **Start now** — they will not give more specification. Then **you make the
  missing decisions**, but you **write them down** with reasoning — never
  silently.

### 2.2 Who answers the brainstorming questions?

- **Autonomous** — the agent decides for itself.
- **The USER** — questions go to them, through you.
- **An external expert model** — another model as an outside expert.

**On the external expert:** its value is that it **can contradict the original
request** if it sees a bad idea or a better path. Do not call it as an echo,
call it as a counterweight. If it contradicts the USER, **do not swallow it**:
put both positions in front of them and let them decide.

### 2.3 The question filter — to the expert, not to the USER

**This step applies when an expert persona is on the team** (see `subagents.md`).
Then the developer agent's questions **do not go straight to the USER** — they
go to the expert first.

**Why.** A developer thinks like a developer and will, in good faith, ask about
things that are actually **professional decisions** — layout, typography,
navigation pattern, component choice. The expert knows those better than the
USER does. Send them all up and the USER gets twenty questions, can genuinely
decide five, and guesses at fifteen — worse guesses than the expert's decisions
would have been.

**How it runs:**

1. The developer writes down everything it would clarify. **It should not
   self-censor** — filtering is not its job. It may mark what it *thinks* is
   professional vs. product-level; that's information, not a decision.
2. **The expert triages.** Two possible answers per question:
   - **"my call"** → it **decides**, and writes the decision down with reasoning
     (this goes into the acceptance form, step 4);
   - **"genuinely theirs"** → it goes into the short list.
3. **The two together** assemble the ONE question round that reaches the USER.

| Goes to the USER | Stays with the expert |
|---|---|
| what we promise the customer | layout, typography, spacing |
| what we leave out | navigation pattern |
| what the priority order is | component choice, hierarchy, motion |
| what costs time or money | how many steps a form is split into |
| anything that, decided wrong, hits the customer | anything the expert knows better |

> **The check, if you hesitate:** *"if I put this in front of the USER, could
> they answer it better than I can?"* If not — don't. Asking is not politeness;
> **every unnecessary question spends their attention**, and takes it away from
> the ones only they can answer.

---

## 3. Full-coverage acceptance criteria

When you hand work to a subagent, define **full-coverage acceptance criteria**.

**They need not be more detailed than what was agreed** — but they must **cover
the whole surface**. Detail and coverage are different things:

- *detail*: how precisely each criterion is written;
- *coverage*: how many dimensions go unmentioned, only to surface later as
  "that's not what I meant".

For a user interface, the whole surface is at least:

- **every screen size** — not only desktop; it must look right on a phone,
- **every display mode** (e.g. light and dark), if the product has them,
- **keyboard and screen reader** — focus, labels, error messages,
- **every affected screen**, not just the one being worked on,
- **error and empty states**, not only the happy path.

> If you deliberately drop a dimension, **write down that you dropped it, and
> why**. A stated gap is manageable; an unstated one is a surprise.

---

## 4. The form — evidence that it is done

**Send a form (`.md`) with every delegated development task**, and require the
agent to **fill it in as part of the work**. An empty form means not done.

Fetch the template: `reference/templates/acceptance-form.<lang>.md`

### Tests are the spine of the form

Type depends on the criterion, and may be a mix:

| Type | Good for |
|---|---|
| **unit test** | pure logic, calculation, validation |
| **end-to-end test** | the real path, in the user's steps |
| **screenshot-based manual test** | what can only be seen: layout, wrapping, mobile |

For every criterion met, the agent returns **the test name**, **what it tests**,
and **what it proved**.

> The third one is the point, and the easiest to fudge. "The test is green" is
> not evidence — the question is **what would have happened if it were broken**.
> So the form asks separately: *can this test fail, and how do you know?* The
> negative control: deliberately break what the test guards, run it, confirm it
> fails, restore it — and **prove it was restored**.

### Planning is measured against the form too

**The agent measures its own plan or design document against the form** while
planning. If the plan doesn't cover a criterion, that should surface at
planning time, not at the end.

### Human check

**Once the agent has filled the form in, run it past the USER.** Not a
formality: the form is worth something precisely because a human looks at it
and says no.

---

## 5. Worktree and branch

**The developer agent always works in its own `git worktree`, on its own branch.**

Two reasons, both learned the hard way:

1. **Concurrent edits.** Two agents in one working tree overwrite each other —
   and your measurement describes a state that has since been replaced.
2. **The working tree lies.** It contains untracked files too. A clean worktree
   contains only what is committed — that is, only what *anyone else* gets.

When the work is finished: the **branch is merged**, the **worktree is cleaned
up**. Leave no debris.

> If the project has a separate release process, merging closes the development
> branch — it is **not** shipping.

**If a release agent merges** (the PR carries `release:queue`) and the PR needs the owner's 👍 or an
urgent merge while the release agent is probably asleep (its next check is far), wake it — in this
order:

1. **Backlog (primary):** a todo task assigned to the release agent's principal: "PR #N: gate/merge" +
   the PR link; for a human approval, a task assigned to the human too. The release agent watches its
   own ball by default; that is what wakes it. In a fleet: `fleet wake <release agent> --reason "PR #N:
   gate/merge" --pr <link>`.
2. **Fallback, only if 1. does not work** (no todo instance, no principal for the release agent, its
   bridge is not running — `fleet wake` exits 3 and prints the text): a peer message (`/rc`).

---

## 6. Reviewers, as needed

Not mandatory, but usually worth it at scale. Use personas from the subagent
inventory (`subagents.md`).

### Customer voice

A **typical user**, or an expert in the specific domain. **Hunts for faults.**

- Reviews **the plan AND the finished version**.
- **Run several rounds** — the first finds the obvious, the second finds what
  broke while fixing the first.
- **Feedback goes into the form**, so the process is auditable both ways: what
  was said, what came of it, and if nothing did, why.

### Adversarial reviewer

An external model in an **adversarial** role: evaluates critically. **Its job is
not to agree.**

---

## What this does not solve

- **It does not replace your judgement.** If the process ran and the thing is
  still bad, it is bad — say so.
- **A filled form does not guarantee quality.** The form is worth something only
  if the tests can actually fail.
- **It does not exempt you from the release process.** Merging is not shipping.
