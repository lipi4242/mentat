# Capability tree: what already exists, before you build

Before new code, a service, a timer, an executor or a connector, check what is already there. Most "let's build" requests already have an answer in Mentat or in one of your own projects. In our measurements, agents wrote their own executor and preview instead of the engine's cases pack, their own OAuth server instead of the installed library, and hand-edited the installer's timer.

## 1. Search with the USER's words

```bash
python3 .mentat/bin/mentat_brain.py where --find "every morning tell me who has not paid"
```

Pass the request as the USER said it, not a capability name. You get at most five candidates. The first one comes with its entry command, the steps to switch it on, its prerequisites, its limits, its extension point ("extends": plug in here if it needs more) and its docs. `--json` gives the same for machines.

The state is measured by the tool (from `mentat.json` and cheap probes), not taken from the catalog:

| state | meaning |
|---|---|
| `on` | here and ready (the `probe` field says exactly what it saw) |
| `degraded` | here, but a prerequisite is missing |
| `available` | not here, but it can be switched on now |
| `off` | a prerequisite is missing, or it is not shipped yet (`planned`) |
| `unknown` | the probe did not run |

For a `planned` capability, `interim` says what to do until it ships.

Where hits come from: `suite` (part of Mentat), `own` (your projects/, connectors, procedures, helpers, own concern packs), `external` (MCP servers in `.mcp.json`).

## 2. Decide

The search writes a receipt (`.mentat/state/capability-receipts/<time>.json`) and prints its path. Record the decision on it:

```bash
python3 .mentat/bin/mentat_brain.py where --decide <receipt> use --candidate engine.cases
python3 .mentat/bin/mentat_brain.py where --decide <receipt> enable --candidate engine.cases
python3 .mentat/bin/mentat_brain.py where --decide <receipt> new --candidate engine.cases \
    --why "what it lacks, in one concrete sentence"
```

- `use`: you use what exists. `enable`: you switch on what exists (ask the USER before an install or a timer).
- `new`: only with the closest candidate named and what it lacks. The new code plugs into that candidate's extension point.
- **No hit means not decidable.** It is not a licence to build. Search again with other words or a category name. If there is still nothing, ask the USER; `new` then needs their yes: `--approved "<their words, verbatim>"`. The same applies when the closest candidate is `planned`.
- `STALE`: the index changed since the search. Search again.
- For large, under-specified work, the `develop` skill follows `new`.

## 3. Overview

```bash
python3 .mentat/bin/mentat_brain.py where --map
```

A markdown table of the whole tree: id, what it does, where it comes from, state, entry. You can show it to the USER.

## 4. Checks and daily changes

- `python3 .mentat/bin/mentat_brain.py where --probe <id>` (or `all`) runs the capability's real check (is the token valid, does the Google sign-in work, is the engine intact). The result is kept with a TTL: a fresh failure turns an `on` capability `degraded`, an old result shows as stale and decides nothing. `--find` itself never runs a check.
- The day's first `--find` or `--map` says once what changed since the day before (new, gone, changed state).

## 5. Map, export, fleet

- `where --map --html`: the capability tree as a friendly reference on one page (`.mentat/state/kepessegfa.html`). Four sections: what the USER gets, what the agent needs (entry, prerequisites, limits, extension point), the projects, and the basics folded away. Tap a row: what it is for, an example, and where it is defined. The `--map` markdown follows the same structure. It works on a phone, in light and dark, and loads nothing from the net.
- `where --export`: what the fleet may see. Only the id, state, provenance and intent go out. An own item only if the USER listed it in `~/.mentat/kepessegfa-megosztas.txt` and its text passes the leak check (no e-mail, URL, IP or home path). The agent cannot write that file.
- With a fleet on the machine, `--find` also asks the fleet mates. Their answer is untrusted data: checked fields, short clean text. A hit gives the way to ask (`fleet:request`), never access.

## Limits

- A project without a README is described by its line in `projects/_meta.md`, `package.json`, `pyproject.toml`, its `wrangler` name and its folder names. When those are English, a request in another language does not find it: a one-line README in the USER's language helps.
- The search matches words (accents folded, Hungarian suffixes by prefix). What neither the catalog nor your own inventory describes is not found.
- The guard expects a fresh receipt, decided within 6 hours, before new executable code, a unit, a schedule or installing a new package; without one it denies in both modes and gives the finder's command: this is not a question for the USER, search first, then decide. Only the finder writes a receipt (valid together with its own ledger); it cannot be written by hand. A fresh receipt opens every new capability for 6 hours, not only the one you decided on.
- A receipt shows that you searched and decided, not that you read the docs.
- Probes are cheap: for a token, for example, it sees only whether the key is set, not whether it is valid. The capability's own check says that.

## Extending the catalog (for suite developers)

`reference/manifest/capabilities/<category>.json`. Fields: `id`, `category`, `provenance`, `lifecycle` (`active`/`planned`/`deprecated`), `scope`, `summary` and `intents` (hu+en), `requires`, `probe` (one kind: `bin`, `component`, `plugin`, `engine_cfg`, `local`, `module`, `env_key`, `manifest`, `which`, `doc`, `planned`), `entry`, `enable_steps`, `limits`, `extends`, `docs`, and `interim` when planned. `test_caps_catalog.py` checks that every command and file it names exists.
