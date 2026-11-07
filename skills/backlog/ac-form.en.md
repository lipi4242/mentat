# The AC form (A–F)

The developer's report on a backlog item: one result for every acceptance
criterion, with evidence, and what the PM needs to decide. It is never written
by hand: `todo item show KEY --form` prints it already filled with the item's
live ACs, and `todo item submit KEY --form FILE` sends it.
(`todo` = `python3 -m anytime_todo.cli`; `--lang hu` prints Hungarian headings.)

```markdown
# WEB-12: The "whose ball" page
<!-- mentat:ac-form item=01JC8Q2W5V round=1 -->

## Meta
- summary: the page lists every open item of the viewer
- head_sha: 3f2c9e1
- pr: https://github.com/example/app/pull/41

## A) Acceptance criteria

### AC 01JC8Q3A1B
> Done when the page lists every open item whose ball is the viewer
- verdict: met
- evidence: test_ball_page_lists_open_items (worker/test/ball.test.ts:18), green

## B) Tests
## C) Review
## D) Gates
## E) Verdict
## F) Attachments
```

## The parts

| Part | What goes in | Who reads it for what |
|---|---|---|
| Meta | `summary` (one line, required), `head_sha` (the commit the evidence is for), one `pr:` line per PR | the PM finds the change |
| A | per AC: `verdict` = `met`, `not_met` or `na`, and `evidence` (a test name, `file:line`, a log line) | the PM checks every row |
| B | which test covers which AC, the command and its result, and whether the test really asserts the AC | is the evidence real? |
| C | the review: the load-bearing claims, challenged, each finding and how it was resolved | what could still be wrong |
| D | the gates of the track, green; a change to a screen needs screenshots | nothing skipped |
| E | **not typed**: on submit it is yes only if every AC is `met` or `na` | |
| F | what is attached (PR, logs, screenshots) | |

## Rules

- **The AC lines are the item's, not yours.** Do not change an `### AC <id>`
  line or the quoted text under it. The id names that AC for life; if the PM
  edits its text, the old form is refused ("changed since the form was made"):
  print a fresh one.
- **Exactly one result per live AC.** A missing, doubled or unknown AC, an
  untouched `met | not_met | na` line, or empty evidence is refused before
  anything is sent.
- **`not_met` is allowed.** Say it plainly with the reason; the PM decides. Only
  an accept needs every AC met.
- **One form per round.** After a reject the next report is the next round:
  print a fresh form. A form of an earlier round is refused.
- B, C, D and F travel as the report's text, headings included; the hints in
  `<!-- -->` are dropped. Evidence may span lines, quotes (`>`) and code blocks.
- **Nothing is dropped silently.** A `## ` line inside a code block is content; a
  second section with the same letter, text typed into E, an unknown Meta line or
  text above Meta is refused, so you can fix it before anything is sent.
