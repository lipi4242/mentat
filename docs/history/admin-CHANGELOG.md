# Changelog

## 0.4.0

First public release. Released together with brain, engine and fleet 0.4.0. It also contains
everything listed under 0.3.0, which was prepared but not published on its own.

- **Todo plugin**: a shared task tree of any depth (a project is simply a top-level todo), with a
  due date and a planned date, labels, comments with `@handle` mentions, an owner and an assignee
  who holds the ball until they hand it back. People and agents use it the same way; an agent signs
  in with a machine token that has the `todo:write` scope and follows a change feed. Every change
  names the revision it was based on, so a stale edit is refused instead of overwriting someone
  else's, and every change is logged.
- **Repeating todos**: daily, weekdays, chosen weekdays, every N days, weeks or months, monthly
  (a day, the last day or the n-th weekday) and yearly, counted from the due date or from when you
  tick it off. Completing one moves the same todo to its next date and reopens its subtasks, so
  missed dates never pile up as a backlog.
- **Todo screens that support, not punish**: a one-line tree with icons, new todos typed straight
  into the tree, finished subtasks struck through in place, five seconds to undo, a repeat picker,
  a readable detail page that keeps your unsaved edit when you comment, and a folded "left over
  from earlier" row instead of red overdue counts. The first start creates you as a participant
  in one click.
- **Your own instance in one command**: `npm run instance:create` runs the README's setup steps in
  order (database, site, API, secrets, migrations, deploy). It picks up where it stopped after a
  failure, never passes a secret on the command line, and `--dry-run` lists the steps first.
  Cloudflare sign-in, the e-mail API key and your own domain stay manual; it prints what is left.
  `npm run instance:seed-principals` adds the todo participants from a file, safe to run again.
- **Tokens made where the agent runs**: `npm run mint-token -- --on <ssh-target> --token-file <path>`
  creates an agent's machine token on the agent's own machine and stores it there (mode 0600, an
  existing file is never overwritten); only its id and hash come back.

## 0.3.0

Prepared but not published on its own; its contents first ship in 0.4.0.

- Cases plugin: API, admin UI and the `cases_cli` command line (markdown or admin backend, sync, export, migrate).
- Connect: one command wires an agent repo to the admin (`connect`, `connect --local`, `--check`, `npm run where`); machine tokens can be issued and revoked.
- Extensible model: custom fields and data models from a single file, `npm run model` (add-field / new in one command) with persistent, committed extensions.
- Local sign-in: login link, UI served from the worker port, `npm run status`.
- Core export and restore: full JSON export of the data and restore from it.
- Product and instance are separate: deploy config is rendered from an instance file; nothing instance-specific lives in the repo.
