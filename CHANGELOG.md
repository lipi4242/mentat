# Changelog

Every release also ships a machine-readable `release.json` at the root of
its tag (see `reference/mentat-json.md`, section 4).

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
    `https://raw.githubusercontent.com/lipi4242/mentat/v0.5.0/INSTALL.md`. The engine, the fleet
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
`https://raw.githubusercontent.com/lipi4242/mentat/v0.5.0/INSTALL.md`. It fetches the 0.5.0
tools; your notes do not change.

Engine: clone the release once
(`git clone --depth 1 --branch v0.5.0 https://github.com/lipi4242/mentat ~/src/mentat`) and
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
