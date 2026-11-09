# Changelog

Every release also ships a machine-readable `release.json` at the root of
its tag (see `reference/mentat-json.md`, section 4).

## 0.6.0

A release for people who run several agents: the fleet now watches itself from one central
place, a manager agent repairs a fallen agent before anyone is woken, and an agent hears about a
todo handed to it within a minute instead of at the next hourly tick. Telegram groups and the
secrets gate are stricter. Read "What behaves differently" and the upgrade order before you
upgrade a server.

- **Central fleet check: one place sees every box, and the owner gets an e-mail when nobody fixes it.** <!-- cap: fleet-check -->
  - Mentat Admin has a new `flotta` plugin. Every box reports its agents' capability probe there
    every 10 minutes (sending, todo, git, own state files, the secrets gate), with its release lag
    and fleet version. A red check opens one incident per agent and check; the next green report
    closes it.
  - A box that stops reporting for 30 minutes opens a dead-man incident. An incident nobody
    resolves within 60 minutes sends the owner an e-mail through the Admin's existing sign-in mail
    sender, again every 6 hours while it stays open, and a short "resolved" when it closes. Every
    threshold can be changed.
  - A box token can only report, only for its own box, at most once a minute; it lives 90 days and
    `fleet doctor` warns two weeks before it expires. A report the Admin refuses no longer counts
    as a sign of life: three refusals in a row open their own incident, and the box's doctor row
    turns red.
  - Without the Admin nothing changes on a server: a red capability goes to
    `~/.config/fleet/state/alerts-undelivered.jsonl` and the doctor's box row is red.
- **Fleet managers: an agent repairs another agent, in a fixed order.** <!-- cap: fleet-managers -->
  - Being a manager is a role. A manager covers one agent, one box or the whole fleet; several
    agents can hold it, ranked. The list lives in one versioned file, `managers.json`, and has one
    writer: `fleet managers check`, `fleet managers publish --dry-run`, `fleet managers publish`.
  - An open incident becomes a todo task for the first fit manager (not the broken agent itself,
    not one whose own box is silent). It claims the incident for a fixed 30 minutes, repairs it
    only through `fleet repair-exec` (five fixed steps: `doctor`, `doctor-fix`, `bridge-install`,
    `unquarantine`, `postcheck`; no free arguments, no shell), and the incident closes only on a fresh, green check made
    after the repair. If nobody claims it within 10 minutes, the next manager gets it. Restarts are
    limited to 3 per hour per agent; after that a human is asked.
  - The `flotta-incidens` skill in the fleet plugin is the manager's instruction. Agents on your
    own computer take part too: `fleet flotta-report` from the session, `doctor` and `postcheck`
    only.
- **Todo wake-up: a handed-over todo reaches the agent within a minute.** <!-- cap: todo-wake -->
  - The Telegram bridge (2.2.0) asks the todo store for the agent's changes every 20 seconds (at
    most 60) and writes one line into the agent's session when the ball is now with it: issued
    to it, handed back, rejected to its developer, waiting for its acceptance, or a comment that
    mentions it. Several events within a minute become one line. No LLM runs for the polling.
  - "Seen, nothing to do": `mentat-todo ack <key> [--note …]`. It is the receipt and wakes nobody.
    A wake-up with neither a reply on the item nor an ack within 30 minutes shows as unhandled,
    and the fleet check turns red.
  - There is no hourly cap, so agents can talk in an item's comments as long as they need. Only an
    obvious runaway (many contentless back-and-forth comments on one item) is held for 5 minutes,
    and that always raises a notice.
  - Without a bridge, the fleet plugin's session hooks run the same code at the start of a
    session and with every prompt; a closed session cannot be woken. Turn it off for one agent
    with `BRIDGE_TODO=off`.
- **The todo command line fills the gaps agents ran into.** <!-- cap: todo-cli -->
  - `task show`, `task list` with filters, `project list`, `task new|update --repeat RULE
    [--repeat-from schedule|completion]` (`--repeat none` clears it), `item resume --note`.
    `task comment` and `task new --parent` accept a backlog key (`WEB-12`).
  - `changes` skips your own writes (see below) and moves the cursor past them, so they never come
    back after an ack. The AC form says what `pr` and `head_sha` expect and refuses a bad value
    before sending it; the Admin's error names the field.
  - `mentat-todo` also works on your own computer, without a server unit: the handle comes from
    the repo's `mentat.json` (`engine.todo_handle`) or `TODO_HANDLE`. A stored token is only sent
    to the API it was stored with.
- **Ask your agent to file a bug report.** <!-- cap: bug-report -->
  - The new `bug-report` skill drafts an issue for the public repository: versions of every part,
    what happened, the steps. Every field is scrubbed (tokens, keys, e-mail addresses, home paths,
    IP addresses, chat ids, phone numbers, account numbers, your private names), and a final check
    on the finished text stops the draft if anything is left. A suspected security problem goes
    only to a private advisory.
  - The agent shows you the draft word for word. It is posted with your own `gh` only after a
    plain yes to that exact draft (its full sha256 must match), at most 3 a day. Without `gh` you
    get a link to file it yourself. It works the same on your computer and on a server.
- **Telegram groups: the sender counts, not only the chat.** <!-- cap: bridge-allowlist -->
  - In the agent's own group, only a sender on `TELEGRAM_ALLOWLIST_IDS` reaches the agent.
    Elsewhere only a private chat with an allowlisted user does; an allowlisted user in a foreign
    group opens nothing, and a message without a sender (a channel, an anonymous admin) never
    gets in.
  - One shared filter removes invisible and control characters (zero-width, bidi, tag characters,
    variation selectors, soft hyphens) from everything that reaches the session: text, captions,
    names, reactions, receipts, and lines left in the queue by an older bridge.
- **The secrets gate blocks less of your own work and more of other agents'.** <!-- cap: secrets-gate -->
  - Your agent can read and write its own project's memory folder (`~/.claude*/projects/<this
    project>/memory/*.md`), also with a heredoc that contains code snippets. Every other part of
    `~/.claude*/projects/` is a secret store: transcripts (your own too), another project's
    memory, file history. "Own project" is the session's project, so a `cd` into another agent's
    repo does not make that repo's memory yours; relative paths after `cd`/`pushd` are checked
    against every directory the command could be in.
  - A path built at run time (`$X`, `$(…)`) that points into a secret store (`~/.claude*`,
    `~/.config`, `~/.mentat`, `~/.ssh`, your home itself) is refused with a request for a concrete
    path. Ordinary repo work with variables passes. A recursive search over a folder with a key
    file is refused with the exclusion that would make it pass.
  - A file's mode alone no longer makes it a secret: only a secret-like name or content does.
    Scripts in an agent's `jobs/` folder and its state files run and read again.
  - `fleet secrets scan` only takes the inventory now. Installing the gate is a separate step
    (`fleet secrets hook install`), which first runs the essentials probe (sending, todo, git,
    own state) against the new gate on one agent, rolls back if that agent turns red, and only
    then writes the rest.
- **`fleet doctor` measures what agents actually do.** <!-- cap: capability-health -->
  - `fleet doctor` and the postcheck after `restart`, `install` and `box-upgrade` run the essentials
    themselves: a dry run of the Telegram send with the unit's env files, `mentat-todo me`, the
    agent's own state files, `git status`. They run in a clean environment, so the operator's
    shell cannot make them green.
  - A failure only in these checks is not fixed by a restart, so it no longer counts towards the
    restart quarantine; it is reported on its own.
  - Every writer of user-level Claude settings (the SessionStart hook, operator skills, the plugin
    install) goes through one canary: one agent first, checked before and after, rolled back on a
    new red. `fleet canary record` records a manual change. The box row shows how far the checkout
    is behind the newest public release.
  - A bridge agent's unit always loads the bridge's env file first, so the agent always has its
    Telegram token.
- **Mentat installs on the Python your Mac already has.** <!-- cap: install-python39 -->
  - Python 3.9 or newer is the one minimum everywhere: the install check, the engine and the
    guides. The Python that ships with macOS is enough.
  - The install guide and the usage pages link the engine and the fleet at the release tag, not
    at the moving `main`. The README says plainly what works on a laptop and what needs an
    always-on server, and what access the Google connection asks for.

Release tooling, for people who build releases: `tools/release/bump.py` moves every version from
`release.json` in one command, and `bump.py --check` is part of the release gate. `publish.sh`
publishes only the gated `main` of the development repository, from a fresh clone, refuses an
empty private-name list unless told otherwise, and checks `main` again just before the push. The
scrub also finds phone numbers, IBANs, tax numbers, bare numeric ids and chat ids. The public
repository has issue forms, a contributing guide, a code of conduct, CodeQL, an OpenSSF Scorecard,
SHA-pinned workflows (with a gate that blocks an unpinned one), and every release ships
`SHA256SUMS` and a signed build provenance attestation. It has no Dependabot pull requests:
dependency updates are made in the development repository and ship with the next release. Each
public CI job is one `.github/ci.sh` call, and the release gate runs the same script on the
composed tree, so a release whose public CI would fail is not published. `publish.sh` waits for
the GitHub Release with `SHA256SUMS` and fails if it does not appear. Test helpers are no longer
listed in the user manifest. `bin/gate functional` runs 47 scenarios of
the todo, backlog and case flows against a throwaway local Admin.

### What behaves differently

1. **Telegram groups.** A group member who is not on `TELEGRAM_ALLOWLIST_IDS` no longer reaches
   the agent; the message only leaves a `drop:` line in the bridge log. Add everyone who has to
   talk to the agent *before* you install the 2.2.0 bridge.
2. **Admin todo API: 401 instead of 403.** An unknown, expired or revoked token now gets 401, as
   on the cases plugin. An `X-Mentat-Token` header that is present but empty is decided on the
   token path (401) and no longer falls back to the session cookie; this also applies to
   `/api/meta`. A live token without the needed scope is still 403, now with a `need` field.
3. **`changes` hides your own writes.** The count of skipped entries is in `own_skipped`; `--all`
   shows everything. `changes --ack` prints JSON. A script that waited for its own write to come
   back through `changes` has to read the item instead.
4. **`ball` hides your own draft items.** `ball --drafts` shows them.
5. **`fleet secrets scan` no longer installs the gate** and never switches a box into merge mode;
   run `fleet secrets hook install` (with `--dry-run` first).
6. **No alert bot.** Capability alerts never go through a Telegram bot; they go to the central
   fleet check, and without it to the undelivered-alerts file. `~/.config/fleet/alert.env` is not
   read.
7. **Engine packs need `<0.7`.** The engine is 0.6.0. A concern pack of your own that declares
   `"<0.6"` is refused; widen it to `"<0.7"`. The bundled packs already do.

### Known security limits

These are known and accepted for 0.6.0. None of them can be used from outside without a token or
a seat on the machine; each has a planned fix.

| Limit | What it means for you | Planned |
|---|---|---|
| All agents on a server run as one system user | The secrets gate, the manager's claim, fencing token and verification nonce keep well-behaved agents from getting in each other's way. They are not a boundary against a malicious agent on the same server, which can read the box token and the claim files. | Per-agent operating-system isolation, after 0.6.0 |
| The secrets gate is a guardrail, not a boundary | It stops mistakes and the usual commands. An agent that deliberately evades it (an interpreter, a path decoded at run time, a path list read from a file, a config the agent can write) is not stopped. | Operating-system isolation |
| The todo wake-up line carries a title | Up to 80 characters of the item's title, written by any todo participant, reach the agent's session, cleaned and framed as data. A model can still read a sentence in it. There is no trust list and, by design, no hourly cap. On the desktop path the title is not yet Unicode-normalised. | The shared filter on the desktop path |
| A bug report's yes cannot prove a person said it | The hash ties the post to the exact draft, but the agent computes it and passes on your answer. The scrubber is not complete (a YAML block value, `key => value`, smart or HTML-encoded quotes, `mysql -p…`, a password written before "is my password"), which is why you read every draft. | Further scrub patterns |
| Release tags are not signed, the plugin marketplace has no ref pin | Tags cannot be moved or deleted (repository rules, immutable releases), and every release has `SHA256SUMS` and a provenance attestation, but `box-upgrade` does not verify a signature yet. | Signed tags and a pinned marketplace ref |
| Some security-relevant parts merge after automated gates only | The bridge, the supervisor, the secrets gate and the bug-report scrubber can be merged without a human review once their gates are green. | Human review for these parts |
| The Telegram check is a dry run | `fleet doctor` checks the token's presence and shape and the send path, not a live call to Telegram. An agent without a declared essentials list passes by default. | A live check |
| A stolen box token can still make noise | It can fill the fleet's open-incident cap (a per-box share limits it) and use Admin storage until you revoke it. It cannot read anything, reach another box's agents, or write instructions into a manager's task. Tokens may be issued for up to 180 days. | Tighter per-box limits, shorter tokens |
| Desktop health is not central | A desktop agent's wake-up health lives only on that computer, and a desktop session reports to the fleet check only while it is open. | Central desktop health |
| No full penetration test yet | 0.6.0 had a targeted security review, regression tests for every fix it asked for, and a differential test of the secrets gate (old vs new, 106 cases). | A full penetration test before 1.0 |

### Upgrading from 0.5.1

Brain only (no server): update from
`https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/INSTALL.md`; your notes do not change.
Run `claude plugin update fleet@mentat` if you use the fleet plugin.

Servers, in this order:

1. **Allowlist first.** Put everyone who has to talk to an agent in a group on that agent's
   `TELEGRAM_ALLOWLIST_IDS`.
2. **The Admin, if you run it.** Export a backup, then apply the migrations `0500_flotta.sql` and
   `0501_flotta_menedzser.sql` (`npm --prefix admin/worker run migrate:remote`; run the 0501
   preflight query from `admin/docs/plugins/flotta/INSTALL.md` first). Deploy the worker, then the
   admin. The worker has a 5-minute cron trigger; e-mail needs the sign-in mail's
   `RESEND_API_KEY` and sender.
3. **Upgrade every box** before you publish any managers: `fleet box-upgrade --to v0.6.0 --dry-run`,
   read the plan, then run it without `--dry-run`. It installs the 2.2.0 bridge and the repair
   steps the managers will call. Then `claude plugin update fleet@mentat` on each box and on your
   own computer (plugin 1.7.0), and `fleet doctor`. If the doctor says a unit does not load the
   bridge's env file, run `fleet install <agent> --dry-run`, then `fleet install <agent>`.
4. **If you use the secrets gate:** `fleet secrets scan --dry-run --agent <agent>`, then the scan
   itself (the old inventory listed scripts and state files), then
   `fleet secrets hook install --dry-run` and `fleet secrets hook install`, and finally
   `fleet canary record`.
5. **Connect each box to the fleet check:** register the box in the Admin (the token is shown
   once), write `~/.config/fleet/flotta.env` (mode 0600) with `FLOTTA_URL` and `FLOTTA_TOKEN`, and
   check that `fleet doctor` says the report is fresh. `~/.config/fleet/alert.env` can go.
6. **Todo wake-up** needs the same `~/.config/todo` setup as `mentat-todo` (`env`, `handles`,
   `<handle>.token` with mode 0600); where `mentat-todo me` works, the wake-up works. On your own
   computer, `node` must be on the `PATH`.
7. **Managers, last.** Mint a token whose only scope is `flotta:config`, put it in
   `~/.config/fleet/flotta-config.env` (mode 0600, `FLOTTA_URL`, `FLOTTA_CONFIG_TOKEN`), write
   `managers.json`, then `fleet managers check`, `fleet managers publish --dry-run`,
   `fleet managers publish`. Managers need plugin 1.7.0 or newer.
8. **Engine.** Re-sync each agent's engine with `~/src/mentat/engine/sync-to.sh <your repo>` and
   the packs it uses, widen your own packs to `"<0.7"`, then `python3 -m anytime_engine.selftest`.

## 0.5.1

A small release for people who run Mentat on a server: upgrading a box is now one command, and
the backlog has a command line for every agent. Nothing breaks when you skip it.

- **One command to upgrade a server.** <!-- cap: box-upgrade -->
  - `fleet box-upgrade --to vX.Y.Z` shows the plan first (`--dry-run`), takes a snapshot, switches
    the checkout (an old directory or a tag), upgrades one agent as a canary before the rest,
    skips agents that are busy or dormant, updates the Telegram bridge only when it differs, checks the
    result and rolls back on its own if a check fails. Each run leaves a receipt in
    `~/.config/fleet/upgrades.log`.
- **`mentat-todo`: the backlog command for every agent on a server.** <!-- cap: mentat-todo -->
  - It works without copying the engine into each agent's folder, and takes the agent's name
    from its unit. Link it once: `ln -s ~/src/mentat/fleet/bin/mentat-todo ~/.local/bin/`.
  - `engine/sync-to.sh <your-repo> --pack todo` copies the backlog pack into an agent folder.
    On a server the pack finds its address, name and token in `~/.config/todo` on its own, the
    same place `mentat-todo` reads.
  - `item list` lists backlog items by project, stage, PM, developer or ball, and
    `item new --parent` takes an item key (`WEB-12`) as well as its id.
- **Fewer false alarms on a server.** <!-- cap: fleet-steadier -->
  - `fleet install` no longer reports a failed restart when the old process was still shutting
    down; the new one is measured, not the dying one.
  - `fleet doctor` shows a bridge that is behind as a to-do (warning), not as an error, and
    flags a bridge whose running process is older than its installed code.
  - A failed `fleet install` restarts the previous unit only if it had restarted it.
  - The plugin's secret guard no longer blocks code that only names a field such as
    `owner_token`, or a sentence that mentions a token; file names like `.env` or `x.token`
    are still blocked. The secret inventory no longer lists an agent's runtime state files
    (`data/state/*.json`) unless they hold a secret-like field.
  - The out-of-memory protection helper `fleet/bin/oom-protect` is now part of the checkout, and
    when it is missing the log names it and the command to install it.

Release tooling, for people who build releases: `publish.sh` is executable, and the smoke test
also works on a plain git clone. The release test stops when the private-name list is missing;
set `MENTAT_ALLOW_EMPTY_NAMES=1` to skip the check on a development machine. Every component gate
runs the private-name check on the tree it ships.

### Upgrading from 0.5.0

Server: `fleet box-upgrade --to v0.6.0 --dry-run`, read the plan, then run it without
`--dry-run`. To give the agents the backlog command, link `mentat-todo` as above. If an agent
uses the backlog, re-sync its engine with `~/src/mentat/engine/sync-to.sh <your repo> --pack todo`
and run `python3 -m anytime_engine.selftest`. Other installs: update from
`https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/INSTALL.md`; your notes do not change.

## 0.5.0

Mentat is now one product: one repository, one version, one install. The brain, the engine,
the fleet and Mentat Admin used to live in separate repositories with their own version numbers.
From 0.5.0 they ship together under one tag of `lipi4242/mentat`, and this file is the one
changelog for all of them. The engine, fleet and admin changelogs up to 0.4.x are kept in
[docs/history/](docs/history/); the brain's history continues below.

- **One repository, one install, one version.** <!-- cap: one-repo -->
  - Every part has moved into `lipi4242/mentat`:

    | Before | Now |
    |---|---|
    | `lipi4242/mentat-ai-bootstrap` | the repository root (same paths: `INSTALL.md`, `reference/`, `skills/`) |
    | `lipi4242/anytime-engine` | `engine/` |
    | `lipi4242/fleet-leader` | `fleet/` |
    | Mentat Admin (not public before) | `admin/` |

    The old repositories stay readable with their tags, so an install that points at them keeps
    working, but they get no new releases.
  - The three-line install prompt now points at
    `https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/INSTALL.md`. The engine, the fleet
    and the admin all come from one checkout of the same tag (`~/src/mentat`), so their versions
    can no longer drift apart.
  - The product version is the only version you need to know. The engine's version follows it,
    so a concern pack of your own must accept `0.5` (see the upgrade steps).
  - The fleet's Claude Code skills are now the plugin `fleet@mentat` from the marketplace
    `mentat` (`claude plugin marketplace add lipi4242/mentat`); before, they were
    `fleet@fleet-leader`.
  - Mentat Admin, the web app for the agent's records, ships for the first time, with its cases
    and todo plugins. It is optional and runs on your computer or on your own Cloudflare
    account. With it, the engine's todo pack works: recurring duties become repeating todos.
- **Todo + backlog: agents hand work to each other.** <!-- cap: backlog -->
  - Todos, cases and backlog items live in one store, the Admin's todo plugin, with one inbox:
    everything that happens to them reaches each agent through one change feed.
  - A backlog item has measurable acceptance criteria. The PM issues it, the developer takes
    it (that is the receipt the PM sees), and the report gives a verdict and evidence for every
    criterion, on the A–F form. The PM accepts, or rejects per criterion with a reason.
  - A case is a one-off process with a goal, a next action and whom it waits on. An agent may
    propose one; a human confirms it.
  - The agent's side is the engine's todo pack: `python3 -m anytime_todo.cli me | ball |
    changes | task | case | item`. The new hourly `todo_labda` concern speaks up only when
    something new is there for the agent or an item was issued to it. The steps are in the new
    `backlog` skill.
  - Moving off Linear: `python3 -m anytime_todo.cli import-linear` brings a Linear team over
    with its keys kept (`ABC-42` stays `ABC-42`) and "Done when" lists turned into acceptance
    criteria; a rerun fills gaps and never duplicates. Try it with `--dry-run` first.
  - The install guide now names the Admin as Mentat's optional todo + backlog.

### Upgrading from 0.4.x

Brain: ask your colleague to update Mentat to 0.5.0 from
`https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/INSTALL.md`. It fetches the 0.5.0
tools; your notes do not change.

Engine: clone the release once
(`git clone --depth 1 --branch v0.6.0 https://github.com/lipi4242/mentat ~/src/mentat`) and
re-run `~/src/mentat/engine/sync-to.sh <your agent folder>` with the packs you use. A pack of
your own that declares `"<0.5"` is refused; widen it to `"<0.6"` and re-sync. The old
`~/src/anytime-engine` copy is no longer used.

Fleet (Linux server): use the same `~/src/mentat` checkout and point the `fleet` command at it
(`ln -sf ~/src/mentat/fleet/bin/fleet ~/.local/bin/fleet`). Then run `fleet setup <agent>` for
each agent, one at a time while it is idle, and wait for exit code 0. Setup rewrites the agent's
units to the new checkout, restarts the agent and its Telegram bridge if they changed, and
switches the plugin to `fleet@mentat`. For a repo that ran `fleet join`, also run
`fleet upgrade <repo>`, which updates its committed `.claude/settings.json`. An agent with a
hand-written unit is not rewritten: change its `~/fleet-leader` paths yourself. Before you
remove the old checkout, check that `grep -rl fleet-leader ~/.config/systemd/user
~/.claude*/settings.json` finds nothing (backup files named `.bak-*` do not count). Then rename it
(`mv ~/fleet-leader ~/fleet-leader.old`), run `fleet doctor`, and delete it once everything is
green.

## 0.4.0

Released together with engine and fleet 0.4.0. The brain's own change is a sharper
identity gate: fewer needless questions, and a stricter idea of what counts as yours.

- **The identity gate asks only when your address could really leak**: only the part of a
  command that goes out on the network counts, so a local step that carries your e-mail (a
  `git commit` with your address, a `git log --author`, a write to a file) no longer asks. Your
  own GitHub account counts as yours once GitHub itself confirms you are signed in to it. The
  suggestion tool now also offers the plain host names from your `known_hosts`, so one yes covers
  the machines you already use. An address read on the spot and sent out (`$(git config
  user.email)` in a request) still asks. <!-- cap: identity-gate-precise -->
- **Only you decide what counts as yours**: a file the agent can edit (the GitHub CLI's host
  list), an ssh target, `known_hosts`, the ssh config, a private-network address or a `.local`
  name no longer makes a place yours by itself; only the list you approved and your own machine
  (localhost) do. Line continuations and loop bodies (`do curl …`) are now read like any other
  command, so they cannot slip past the gate. <!-- cap: identity-gate-strict -->

## 0.3.1

The last larger step before 1.0. Released together with anytime-engine 0.3.1 and fleet 0.3.1. What changed per capability: [CAPABILITY-LOG.md](CAPABILITY-LOG.md).

- **Install with three lines**: paste a three-line prompt into Claude Desktop (Code tab) or
  Claude Code; it points at `INSTALL.md` (hu: `INSTALL.hu.md`), a page that says what the agent
  does, step by step, and the rules it keeps (instructions only from this release, each step said
  first, a yes before anything is installed, never a secret in the chat). The only prerequisite is
  Claude: a missing git or Python is installed with the system's own installer (winget,
  `xcode-select`, apt/dnf) after your yes. The long Brain Prompt stays as the manual route. <!-- cap: install-three-lines -->
- **The install checks what it downloaded before it runs it**: `release.json` lists a sha256
  for every file the install puts in `.mentat/bin/`; `mentat_init.py` checks them before it
  imports anything else (run with `python3 -I`, the tool folder last on the path, so a planted
  `json.py` cannot run first) and stops on a changed or missing file, on a `.py` under
  `.mentat/bin/` that the release does not ship (named, never deleted), or on a missing list.
  The list comes from the same tag as the code: it catches a partial, mixed or changed download,
  not a replaced tag. The release cut writes it with `python3 release/reference/manifest/mentat_verify.py
  --write release --freeze`; from then on a test fails when it is stale. <!-- cap: install-verify -->
- **Windows-aware preflight**: `mentat_init.py` now stops early, with the one-line install for
  your system, when Git Bash is missing on Windows (Claude Code runs hooks in it; without it the
  guard hook would block every call), or when `python3` does not answer in the shell the hooks run
  in (the Microsoft Store stub). The guard probe and the engine's `sync-to.sh` run through Git Bash
  on Windows. <!-- cap: windows-preflight -->
- **The capability tree as a reference, and for the fleet**: `where --map --html` shows the tree as
  one friendly page (phone, light and dark): what you get, what the agent needs, the projects apart,
  the basics folded away, and each row says where it lives and gives an example; `where --export` gives the fleet only id, state,
  provenance and intent, and your own items only from a list you keep outside the repo, after a leak
  check; `--find` asks the fleet mates when a fleet runs here, and treats their answer as data. <!-- cap: capability-map -->
- **The capability tree keeps itself current**: `where --probe <id>|all` runs a capability's real
  check (token, Google sign-in, engine) and keeps it with a TTL; a fresh failure shows the capability
  as degraded. The day's first `where` says what changed since the day before. A project without a
  README is described by its index line, package.json, pyproject and wrangler names. <!-- cap: capability-probes -->
- **The install says what it found**: `mentat_init.py` lists what was already in the folder
  (notes, tables, code, signs of a half-finished app, another agent's instruction file), what
  went into its first commit, and your uncommitted changes file by file, which it leaves alone
  until you decide. It uses the git identity you already have; if there is none it asks for
  the name and e-mail on your saves instead of making one up. <!-- cap: install-summary -->
- **"Next week" is asked, not guessed**: `mentat_dates.py` turns a time phrase into dates in
  your time zone. When it can mean more than one range ("next week": the calendar week or the
  next 7 days?) it lists them and the agent asks you; what it does not understand, it says so. <!-- cap: dates-asked -->
- **Your address does not go to third parties**: a call that goes out on the network (shell,
  web fetch, web search, an MCP tool) with your e-mail in it, to a place that is
  not yours, is asked from you, and denied headless. You decide which
  places count as yours; that list is written only with your yes. <!-- cap: identity-gate -->
- **The guard holds the capability tree**: new code, a service, a schedule or a new package
  needs a fresh look at what already exists first (`where --find`, then `--decide`); the agent
  resolves it, you are not asked. <!-- cap: guard-capability-tree -->
- **Google through one tool**: invitations, mail, sharing and sheets go through
  `mentat_google.py`, checked against your approved agreement before anything is sent: only
  the agreed people, guests who cannot see each other (unless you said so), an explicit choice
  of who gets a notification, sharing by name only, and a read-back of what Google now holds.
  Several outside mail recipients go in Bcc only for a private group mail; otherwise you are
  asked. Sign-in uses Google's own library (`mentat_google_auth.py`), also when the agent runs
  on a server and your browser is elsewhere; the secret lives in one place, `.secrets/google/`. <!-- cap: google-connector -->
- **What already exists, before you build**: `mentat_brain.py where --find "<the request>"`
  searches a curated catalog of what the suite can do (switched on or not, and what is planned)
  plus your own projects, connectors, procedures, helpers and concern packs, and writes a receipt;
  `where --decide` records use / enable / new on it (new needs a reason, and the USER's yes when
  nothing fits); `where --map` prints the whole tree as a table. State comes from mentat.json and
  cheap probes, never from the catalog. Guide: `reference/capabilities.md`. <!-- cap: capability-tree -->
- **What you agreed is kept in a file and checked before it goes out**: for a list, an
  export or a message to several people, the agent records the agreement (columns, what stays
  out, who receives it, the dates with a time zone, the defaults) with `mentat_contract.py`,
  and it counts only after your yes, quoted word for word; a material change needs a new yes.
  Before it sends anything or calls it done, `mentat_accept.py` checks the output against it:
  exactly the right records, nothing left out slipped in, every date inside the window, only
  the agreed recipients, who cannot see each other. Red means it does not go out. <!-- cap: agreement-and-acceptance -->
- **Direct database writes need you**: writing to a database directly waits for your yes, and
  is denied when nobody is there to ask. <!-- cap: database-write-gate -->
- **Install in one call**: `mentat_init.py`: preflight (git, python, Claude Code
  2.1.295+, disk, network), the skeleton with the guard hook, the identity placeholders,
  mentat.json, git identity for this folder, the engine pinned to the release tag with
  `--pack cases` and no timer, the first commit and a selftest (the guard is probed with
  an outside read), then a short summary ending in `MENTAT-INIT OK`. <!-- cap: install-one-call -->
- **The guard works from the first session**: reading outside the working folder and dangerous
  steps are asked from you in an interactive session, and denied when nobody is there to ask.
  What you approve is remembered, every decision outside the folder is logged, and if the guard
  itself cannot run, the call is blocked. <!-- cap: working-folder-guard -->
- **Tools for publishing a page**: `mentat_web.py check` asks the page the
  way you see it (your Access cookie or a service token) and says `OK` or `FAIL`; `mentat_web.py
  deploy` goes live only with your quoted yes and then reports `LIVE <address>` or `NOT LIVE`;
  `mentat_cf_access.py` puts Cloudflare Access in front of the Worker through the API;
  `mentat_cf_token.py` walks you through the API token one or two steps at a time and checks each
  one. The web guide follows today's Cloudflare screens, uploads the whole tidied list (a doubtful
  row is a status, not a filter) and tries the first deploy signed in. <!-- cap: web-tools -->
- **The model switch says what leaves**: before it moves to another model, the agent tells you
  that everything it reads from then on goes to OpenRouter and the routed provider, and asks you
  to allow only zero-data-retention endpoints there. <!-- cap: model-privacy -->
- **Taking over a business reads less**: the inventory lists file names without downloading the
  excluded files in a partial clone; `folder/**` excludes a folder at any depth; a source without
  a path gets a readable reason; the always-loaded rules offer the onboarding guide from the first
  session and read nothing outside the folder before it. <!-- cap: takeover-safer -->
- **"What is due" says when and who**: `mentat_brain.py due` shows the time of a deadline and the
  people the note links to, next to its source. <!-- cap: due-with-time -->
- **Fewer silent assumptions**: when a requested field list changes, the agent reads it back
  again and adds no field nobody asked for; before it moves a case's date or state, it reads the
  case's notes and conditions and asks when they conflict. <!-- cap: rules-readback -->
- **The status and the engine line tell the truth**: `status` no longer recommends the unreleased
  admin, and the always-loaded intake installs the engine with `--pack cases`, so its setup is
  complete. <!-- cap: status-honest -->
- **Local pages that never stall the conversation**: a page, a preview or a dev server on your
  computer starts in the background. The agent checks that it opens and gives you the address, and
  it stops by itself after an hour. <!-- cap: local-pages -->
- **Keys go into a hidden form, not the chat**: when a service needs a key, you paste it into a
  small local form and it is saved in a private project file. If you already pasted one into the
  chat, the agent stores it at once and suggests making a new one. <!-- cap: key-form -->
- **A download that does not match the release is not installed**: the install tries once more,
  then stops and tells you in plain words, with nothing left half installed. A network error is
  reported as a network error, and you can simply retry. <!-- cap: install-mismatch-stop -->
- **Missing parts are named, not replaced**: after an install that stopped, the agent lists which
  parts of Mentat are there and which are missing, and offers to install the missing one.
  <!-- cap: install-parts -->
- **An existing AGENTS.md is kept**: installed into a folder that already has one, Mentat leaves
  your text as it is and adds its own sections at the end. <!-- cap: takeover-agents-md -->
- **"Done" means checked where you use it**: before calling work done, the agent checks the
  address you got (and that a private page asks for sign-in), the file, or the last scheduled run
  and whether it holds what it promised. When it could check only on its own machine, it says so.
  <!-- cap: done-check -->
- **Unsaved work and stray keys are mentioned**: the same check tells you about unsaved changes,
  pages still running, and keys found in files that git keeps. <!-- cap: done-tells-more -->
- **A new session starts with your schedule's state**: if the last scheduled run did not happen,
  failed, or left out what it promised, the agent tells you first. <!-- cap: schedule-at-start -->
- **Nothing final goes out unseen**: before something is sent, recorded or created somewhere else,
  the agent reads it back to you in full, with every required field filled in. It goes out after
  you reply with the short code it shows, and the agent then checks what arrived.
  <!-- cap: final-preview -->
- **Going live checks the Cloudflare token first**: before a deploy, the agent checks that the
  token has every permission this project needs and names what is missing and where to fix it.
  After the deploy it checks that the page asks for sign-in. A Cloudflare API gateway or proxy
  works when `CLOUDFLARE_API_BASE_URL` and `MENTAT_CF_API_ALLOW_HOST` are set in the environment.
  <!-- cap: cf-preflight -->
- **The agent does the technical steps itself**: it does not ask you to run commands or edit files
  it can handle. You only get the steps that need a person, such as signing in, paying, or typing a
  key into the form. Telegram agents work the same way. <!-- cap: agent-does-steps -->

### You need to (from 0.3.0)

Update Claude Code to 2.1.295 or newer (`claude update`), fetch the 0.3.1 tools (BEKOTES step 0),
then run once in the agent folder: `python3 .mentat/bin/bekotes/szerep_hook.py --harden`. It makes
the guard block a call whenever the guard itself cannot run. Running it again changes nothing;
`fleet doctor` shows any agent still to update.
Then run `python3 .mentat/bin/mentat_scaffold.py --lang <en|hu>` once: it adds the new hooks and
the new AGENTS.md sections, and changes nothing else.

## 0.3.0

0.2.0 was never published; its changes ship here.

- **Subagents**: reusable personas with their own brain and history, and
  the development process for large, under-specified work (`skills/develop`,
  `skills/subagent`).
- **Cheaper brain sessions**: `mentat_brain.py due` is compact by default (8 lines, `--full`), `find` shows deadlines, and new `mv` (rename + links + index), `commit` and `where` replace multi-turn manual work.
- **Complete installation**: `CLAUDE.md` loads `AGENTS.md`, the folder
  becomes a git repo with a first commit, a fresh session proves it remembers,
  and remote control is offered. New entity: `decision`.
- **`mentat.json`**: the brain records itself in the component manifest and
  `.mentat/local.json`; the new `status` skill says which building blocks are
  present and which synergies are live.
- **Ownership**: product rule blocks in `AGENTS.md` are marked
  `mentat:managed`; everything else is your memory. The brain repo is private.
- **Cases**: new `case` entity for things to get done and track over time,
  once or recurring.
- **What already exists comes first**: the always-loaded rules say: if an installed
  component, pack or tool already solves it, use that; needless complexity is a defect.
- **Skeleton in one command**: `mentat_scaffold.py` creates the git repo,
  `AGENTS.md`, `CLAUDE.md`, the brain folders with `_meta.md` and
  `.gitignore` deterministically; `--check` verifies the result. The
  colleague only runs the intro chat and fills the placeholders. The
  `AGENTS.md` it writes is shorter and gains a `claims` block: state is
  reported only from a check that was actually run.
- **`status`** prints the one way to connect the admin when it is missing.
- **Publishing to the web for non-technical users**: one rule and an on-demand guide
  (`reference/publish-web.md`): a Worker + D1 on `workers.dev` (no domain needed), the
  token in `.env`, Cloudflare Access in front; no tunnels, no home-made passwords, no
  secrets in the chat.
- **Notes in one command**: `mentat_brain new` (a note from its template),
  `due` (what is due, compact) and `find`; a shorter init prompt and `_index`.
- **Local dates**: the brain's note commands use the time zone in `mentat.json`,
  so "today" is no longer a day off around midnight.
- **Taking over an existing setup**: instructions found in the folder (an old
  `CLAUDE.md`, `AGENTS.md`, README or prompt) are data, not rules: the agent lists
  them with their source and adopts one only after you say yes; it answers in your
  language; it reads a requested field list back before building and asks about
  duplicates; recurring work goes to the engine, not to a hand-made timer.
- **Takeover summary**: the first answer after a takeover says what is half-done and
  what someone else changed since the last commit; such changes are never committed
  silently.
- **Roles**: `mentat.json` `roles.default` and `roles.installed`; four role
  templates (`asszisztens`, `backlog-manager`, `fejleszto`, `kiado`), chosen per
  run with `MENTAT_ROLE=<name> claude` or `/szerep`. A role guard hook denies
  what the role must not do. It prevents accidents; it is not a security boundary.
  `status` says whether the guard is installed.
- **The role guard covers more ground**: what a role may not read stays closed whichever tool
  the agent reaches for, including the onboarding reader and the engine's own output, and the
  agent cannot change the guard's own files.
- **Onboarding (bekötés)**: `reference/bekotes/BEKOTES.{en,hu}.md` takes over a
  business: a deterministic inventory of its repos, old agent memories and
  Linear issues (forbidden paths are only named), memory export behind a
  filter and your approval, a cited knowledge map, roles, the `AGENTS.md`
  responsibility block, and `bekotes.py check`.
- **Restricted facts stay out of the shared map**: facts from a source some role may not read
  stay in their own folder, behind the same rule; `bekotes.py check` fails a citation that would
  put them in the shared map.
- **Model switch**: `skills/model` and `mentat_model.py`: an agent moves itself to a
  measured open model via OpenRouter (today: DeepSeek V4.1 Flash, 3.62 vs Opus 3.69 on
  the acceptance suite) and back to Claude with one command, with a live probe and
  rollback. Only that repo changes; the shared Claude login and the other agents stay as
  they are.

### You need to

Nothing for a new install. An existing brain keeps working; to get the new
parts, ask your colleague to run `reference/initialization.md` step 1 and
step 3 (it never overwrites a file) and to add the `mentat:managed` markers to `AGENTS.md`.

## 0.1.2

Earlier releases were published without a changelog.
