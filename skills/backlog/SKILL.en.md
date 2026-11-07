---
name: backlog
description: Work in the shared work store of the Admin (todos, cases, backlog items with acceptance criteria) as a backlog manager (PM), as a developer, or as the owner of a case. Use when you hand work to another agent or take work from one, when someone asks whose ball something is, and on every tick that plans `todo_labda`.
---

# Skill — `backlog`

**Invoke when** you give work to someone (another agent, or yourself as the
developer), take work given to you, decide whether finished work is accepted,
track a long process as a case, or the plan contains `todo_labda`.

One store, one inbox: todos, cases and backlog items live in the Admin's todo
list, and everything that happens to them reaches you through `changes`.
**The ball** is whoever has to act next. Your token is your identity: every
write is yours, and you can never write as anyone else.

All commands run from the repo root: `python3 -m anytime_todo.cli …` (below: `todo …`).

## Step 0 — Is it there?

`todo me` prints your principal. If it says the pack is not configured, this
agent has no Admin yet: tell the USER that the Admin is the **todo + backlog**
of Mentat, and offer it (`admin/README.md`, "Connect your agent"). Do not keep a
backlog in markdown files instead without their yes.

## Step 1 — Your inbox, on every tick

1. `todo changes` — the events for you after your cursor, oldest first.
2. Handle each: answer a question or a mention (`todo task comment ID --text …`),
   act on what became yours (`todo ball` lists everything whose ball is yours).
3. Only then: `todo changes --ack <last_seq>`. Never ack what you have not
   handled. A crash before the ack only means you read the same events again.

## Step 2 — As the PM (the item's owner)

An item moves: `draft` → `issued` (given out) → `taken` (the developer started)
→ `review` → `done`; and `hold`, `dropped`. You own the item from start to end.

1. **Write it so that someone else can do it:** `todo item new --project KEY
   --title … --description …`. The description says why, what is in scope,
   what is **not** in scope, and who decides. Put the requester's exact words
   in `--quote` (and where they said them in `--quote-ref`).
2. **Make every acceptance criterion measurable:** one `--ac "Done when …"` each
   ("on a 390 px screen the labels do not overlap their dots"). An AC keeps its
   id for life; change its text with `item ac-edit`, never by deleting and re-adding.
3. **Issue it:** `todo item issue KEY --dev <handle>` (you may be the developer).
   Look at items that stay `issued` and are not taken; ask the developer once,
   in a comment, never on a timer.
4. **Decide on the report.** `todo item show KEY` shows each result next to its
   AC. Check every result against its evidence (open the test, the file, the PR).
   - All met or n/a and the evidence holds: `todo item accept KEY --checked`.
   - Otherwise: `todo item reject KEY --fail AC_ID="what is missing" … --note …`,
     one `--fail` per AC that does not pass. The item goes back to the developer.
5. `hold` (needs a decision first), `resume`, `drop` (will not be done): each with `--note`.

## Step 3 — As the developer

1. **Take it when you start:** `todo item take KEY`. That is the receipt the PM sees.
2. **Cannot or should not do it:** `todo item handback KEY --note "<why>"`. Do not sit on it.
3. **When it is done:** `todo item show KEY --form [--lang hu] > form.md`, fill it
   (`ac-form.en.md`), then `todo item submit KEY --form form.md`.
   - Give evidence for **every** AC. An AC you did not meet is `not_met` with
     the reason: say it plainly, the PM decides.
   - Link the PR in the form's `pr:` line, and write its state from `gh pr view`.
4. After a reject, get a **fresh** form: the next report is a new round.

## Step 4 — Cases (a long, one-off process)

1. **Propose, a human confirms:** `todo case new --title … --goal "<what done
   means>" [--frame …] [--next-action …] [--waiting-on …] [--review-every 7]`.
   A case you create is a proposal until a human confirms it. A recurring
   obligation is not a case.
2. `next_action` is **your** next step; `waiting_on` is who you chase outside
   the store. Keep both current with `todo case update ID …`.
3. Each tick: `todo case review-due`; look at each, act, then `todo case review ID --note …`.
4. Close it deliberately: `todo task done ID --children close|keep` decides what
   happens to its open todos. An open backlog item under it must be accepted or dropped first.

## Never

- Write as a person, or put a person's name on your own words.
- Chase anyone on a timer, or nudge more than once without new information.
- Accept an item whose evidence you did not check.
