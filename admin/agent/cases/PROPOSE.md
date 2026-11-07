run: `python3 .mentat/bin/cases_cli propose-scan` — the whole brain condensed (path | title | dated frontmatter | the dated sentences); read that instead of `cat`-ing the notes.

# After install: propose the cases that already live in the brain

For the agent. Installed as `.mentat/cases-propose.md` (INSTALL step 0); run it
once the user agreed what a case is (INSTALL step 1, `<brain>/cases/_meta.md`).
Speak to the user in their language. **Nothing goes into the cases before the
user has approved it.**

## 1. Look through the brain

`propose-scan` lists every note under `<brain>/` (not `<brain>/cases/`, those are cases already); open a note only when its line is unclear or its title hints at a deadline (`--full` = every dated sentence):
todos, procedures, brain dumps, explorations, decisions — and **people**: notes
about employees, suppliers and family often hide a deadline ("probation ends on
the 30th", "the order must be in by Monday noon").

A case, by the agreed definition: something that gets done (or each occurrence
does), has a next step and a date. One note may hold several; one note may hold
none. **Not a case:** a done or cancelled todo; an idea with no date; a plain fact
about a person; something that already happened; a preference or a decision with
nothing left to do; contact details.

## 2. Write the proposal

`.mentat/cases-proposal.json`, one item per case:

```json
{"schema": 1, "items": [
  {"id": "p1", "source": "<brain>/people/reka.md", "title": "Réka's probation ends",
   "description": "Three-month probation, ends on 30 Nov.", "next_action": "Decide, then talk to her",
   "kind": "one-off", "due_at": "2026-11-30", "reason": "A dated decision about an employee."},
  {"id": "p2", "source": "<brain>/procedures/payroll.md", "title": "Payroll preparation",
   "description": "Timesheets to the accountant.", "next_action": "Send the timesheets",
   "kind": "recurring", "recurrence": "monthly:5", "anchor_at": "2026-11-05", "reason": "Every month by the 5th."}
]}
```

- `source`: the note's path from the repo root; `id`: short and unique.
- `kind`: `one-off` with `due_at`, or `recurring` with `recurrence`
  (`monthly:<1-31>`, `quarterly:<1-31>`, `yearly:<MM-DD>`, `weekly:<mon..sun>`)
  and `anchor_at`, the first due date on or after today (for a quarterly one it
  also sets which months).
- `own` (optional): values for the admin's own case fields, e.g.
  `"own": {"priority": "high"}` — only names `cases_cli fields` lists; on the
  markdown backend they land in the case's `extra`.
- Dates come from the notes. A case whose date you cannot pin down stays out of
  the file: list it to the user as *unsure* and ask.

Then: `python3 .mentat/bin/cases_cli proposal check` — fix until it says `ok`.

## 3. Show it, wait for the answer

A short numbered list, one line each: title — when (the date, or "every month on
the 5th") — next step — from which note — why. Then the unsure ones. Ask which to
bring over. Do not create, move or edit anything until the user answers.

## 4. Import what was approved — only that

```bash
python3 .mentat/bin/cases_cli import --from .mentat/cases-proposal.json --only p1,p2
```

Each approved item becomes a case in `<brain>/cases/` (title, description, next
step, date or rhythm; the file names the source), and the source note gets a line with the case's
`brain_ref`; the note itself stays where it is. A rerun does not duplicate. Leave
the proposal file in place: it records what was offered.

Then close occurrences that are already done (INSTALL step 2) and tell the user
in two lines what is now tracked.
