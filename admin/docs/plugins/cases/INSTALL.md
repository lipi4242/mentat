# INSTALL — cases

For the agent. Step by step **with the user**; nothing happens silently.
Every command runs in the agent repo (the one with `mentat.json`).

## 0. The CLI

Binding the admin (`npm run connect -- … --local --plugins cases --migrate-brain` in ~/src/mentat/admin/worker) already
copies `cases_cli` to `.mentat/bin` — then skip the clone below.

```bash
[ -d ~/src/mentat ] || git clone --depth 1 https://github.com/lipi4242/mentat ~/src/mentat
mkdir -p .mentat/bin && cp -R ~/src/mentat/admin/agent/cases/cases_cli .mentat/bin/
python3 .mentat/bin/cases_cli status
```

No `mentat.json` → install the brain first. A newer `schema` than the CLI
knows → stop and tell the user; write nothing.

## 1. One case — the everyday path

```bash
python3 .mentat/bin/cases_cli add --title "Gas bill" --due 2026-11-10 --recurrence monthly:10 --next "Pay by transfer"
python3 .mentat/bin/cases_cli add --title "Tax return" --due 2027-05-20 --next "Send it in"
```

`add` writes into the configured backend (markdown or admin) and says which
(`written to: …`). With `--recurrence` the `--due` date is the first one.
A first month off the rule stays in the series: `--recurrence monthly:10 --due 2026-10-20`
= October on the 20th, then every 10th (one case; `update <id>` takes the same two flags).
Recurrence: `monthly:<1-31>`, `quarterly:<1-31>`, `yearly:<MM-DD>`,
`weekly:<mon..sun>`. Paid already: `cases_cli close <id> --note "paid"`
(the earliest open occurrence first).

## 2. What a case is — agree it once

Propose, let the user change it, write it to `<brain>/cases/_meta.md`:

> A case has **a done state** (or each occurrence can be done), **a next step**
> and **a date** (deadline, or when to look again). Not a case: a project, a
> one-step todo, an area of life.

## 3. Post-install review (required, also on update)

This step runs even if the plugin was already installed or was just updated:
a "post-install review" means this, not a `sync` and not printing the list.
Look through the whole brain and propose the cases hiding in it:

```bash
cp ~/src/mentat/admin/agent/cases/PROPOSE.md .mentat/cases-propose.md   # if not there yet
python3 .mentat/bin/cases_cli propose-scan          # the brain condensed: dated sentences
# following .mentat/cases-propose.md: write .mentat/cases-proposal.json
python3 .mentat/bin/cases_cli proposal check        # schema check
```

Show the list to the user and **wait for the answer**. Import only the approved
items (the source note stays in place and gets a `brain_ref`):

```bash
python3 .mentat/bin/cases_cli import --from .mentat/cases-proposal.json --only p1,p3
```

## 4. With an admin — cases live there

Bind it from the admin checkout (`~/src/mentat/admin/worker`, its README *Connect
your agent*); never start it by hand, never put the token anywhere else:

```bash
npm run connect -- --repo <this repo> --url http://localhost:8787 --local --plugins cases --email <owner>
```

**Rule, no question to the user:** an admin bound with `--plugins cases`
means the admin is the record. Right after connect:

```bash
python3 .mentat/bin/cases_cli migrate --to admin --dry-run   # one line to the user: what moves
python3 .mentat/bin/cases_cli migrate --to admin             # all or nothing; a rerun finishes it
```

From then on `add` writes to the admin. An unreachable admin is exit 3, never
a fall-back to files. `cases_cli sync` at session start (context up, the
user's admin edits down). Back: `migrate --to markdown`; a copy: `export --out DIR`.
Sign-in link and the admin's real state: `npm run login-link`, `npm run status`
in `~/src/mentat/admin/worker` — quote `status`, not memory.

## 5. Reminders — the engine

With `components.engine`: install the cases pack as the engine's
cases-pack guide (in the engine's repo) says; agree the warning window
(`ANYTIME_CASES_WARN_DAYS`, default 3). No engine: say plainly nobody will
remind on time, and run `cases_cli due` at every session start.

## 6. Check, then tell the user in two lines

```bash
python3 .mentat/bin/cases_cli list --status all
python3 .mentat/bin/cases_cli due --days 7
```

More fields or a data model of their own: `agent/EXTENDING.md` in the admin checkout.
