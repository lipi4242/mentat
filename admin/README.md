# Mentat Admin

**A small web app where your AI agent keeps its records (cases, deadlines, todos, anything you add) and where you can see and edit them, on your laptop for free or on your own Cloudflare account.**

[![Release](https://img.shields.io/github/v/tag/lipi4242/mentat?label=release)](https://github.com/lipi4242/mentat/tags)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Mentat Admin is the optional part of [Mentat](../README.md#whats-inside): the rest of
Mentat runs without it, and it comes in the same checkout. It is a
pluggable admin surface with no model calls of its own, built on Cloudflare (a
Hono worker with D1 SQLite, and a Refine/Ant Design SPA on Pages). The core is
small: e-mail sign-in, machine (agent) tokens, plugin registration with
per-plugin migration bands, a generic CRUD layer, an audit trail, and a JSON
export of everything it stores. Plugins add the domain: cases (see
[the cases plugin guide](docs/plugins/cases/INSTALL.md)) and the todo list the
engine reads for recurring duties.

## Quickstart: look at it on your machine (about a minute and a half)

Needs Node.js 22 or newer and git. No Cloudflare account, no agent. If you already
have `~/src/mentat` (the engine and the fleet use the same checkout), skip the clone
and run `git -C ~/src/mentat fetch --tags && git -C ~/src/mentat checkout v0.5.1`.

```bash
git clone --depth 1 --branch v0.5.1 https://github.com/lipi4242/mentat ~/src/mentat
cd ~/src/mentat/admin
npm ci --prefix worker && npm ci --prefix admin     # most of the time
npm --prefix admin run build                        # the UI the worker serves
cp config/dev.vars.example worker/.dev.vars         # local-only secrets
cd worker && npm run migrate:local                  # creates the local database
npm run dev:local                                   # API + UI on http://localhost:8787
```

In a second terminal, from `worker/`:

```bash
npm run login-link -- --email admin@example.com     # a one-time link; open it in your browser
```

The link works once, for 10 minutes, on this machine only; the e-mail is the
default `ADMIN_EMAILS` of `worker/wrangler.toml`. Tests need no account either:
`npm --prefix worker test` and `npm --prefix admin test`.

## Connect your agent

One command does the whole local setup for an agent repo (the quickstart steps,
a service that keeps the admin running, a token, the CLI, and the notes the
agent reads) and ends with a short block you can quote. It needs `git`,
`curl`, `python3` and Node.js 22 or newer; the second line installs Node for
you, without sudo, if it is missing or too old.

```bash
cd ~/src/mentat/admin                               # the checkout from the quickstart
node -v 2>/dev/null | grep -qE '^v(2[2-9]|[3-9][0-9])' || { sh worker/scripts/install-node.sh; export PATH="$HOME/.local/bin:$PATH"; }
npm ci --prefix worker && npm ci --prefix admin
cd worker
npm run connect -- --repo ~/agents/my-agent --url http://localhost:8787 --local --plugins cases --email owner@example.com
```

It ends with a short block: done / next / sign in / the list URL of the
cases. `--check` changes nothing and lists what is missing; a rerun is safe
(a token the admin still accepts is kept, a current `cases_cli` and AGENTS.md
block are left alone). Day to day:

| what | command (in `worker/`) |
|---|---|
| open the admin (UI + API, one port) | the URL it printed, e.g. http://localhost:8787 |
| sign in (no mailbox, no log) | `npm run login-link` → a link valid once, for 10 minutes, on this machine only |
| the real state (URL, port, commit, migrations, tokens) | `npm run status` (**quote this, nothing else, when you report**) |
| which models and fields exist, and their list/form URLs | `npm run where` |

What `connect --local` does: node on the login PATH (`~/.local/bin`);
`worker/.dev.vars`; builds the UI; migrates the local D1 (backup first);
installs the systemd user unit `mentat-admin.service` (API + UI on the URL's
port, at boot via linger); waits for `/api/health`; mints the agent's token;
vendors `cases_cli` into `<repo>/.mentat/bin`; writes the managed block
(`<!-- mentat:admin:start -->`…`end`) at the END of `<repo>/AGENTS.md`; with
`--migrate-brain` moves the brain's cases into the admin. No systemd (macOS):
it says so; run `npm run dev:local -- --port 8787` yourself. Logs:
`journalctl --user -u mentat-admin.service`. The server is on 127.0.0.1 only;
from another machine use an SSH tunnel (`ssh -L 8787:localhost:8787 <box>`).

The API by hand (curl, a demo token): [docs/local-api-by-hand.md](docs/local-api-by-hand.md).


## Deployables

- `worker/`: Hono API on Cloudflare Workers, backed by a D1 database.
  Handles auth (e-mail OTP), agent tokens, and plugin routes (`worker/src/plugins/`).
- `admin/`: React + Refine + Ant Design SPA on Cloudflare Pages, with a
  Pages Function (`admin/functions/api/`) that proxies `/api/*` to the worker
  so the sign-in cookie stays same-origin.

## Product vs. instance

This repo holds the **product** only. Everything that belongs to one
installation lives in an **instance file** outside git:

| Where | What | In git? |
|---|---|---|
| `config/plugins.ts` | which plugins the build compiles in | yes (product) |
| `worker/wrangler.toml` | product + local-dev config; no account, fake D1 id | yes (product) |
| `config/instance.example.json` | the instance file's shape, made-up values | yes |
| instance file (`instance.json`) | title, Cloudflare account id, D1 id, allowed origins, admin e-mails, OTP sender, site URL, Pages project | **no** |
| `config/rendered/wrangler.toml`, `admin/.env.production.local` | generated from the two above at deploy time | **no** |

`config/instance.mjs` looks for the instance file in this order:

1. `$MENTAT_ADMIN_INSTANCE` (an explicit path; a wrong path is an error, not a fallback)
2. `config/instance.json` (gitignored)
3. `~/.config/mentat-admin/instance.json`

`npm run deploy` (worker and admin) renders the deploy config from it first.
A plain `wrangler deploy` of the committed `worker/wrangler.toml` fails at the
D1 binding on purpose: it has no real database to bind.

Secrets are never in the instance file: they are Wrangler secrets on the
worker (`BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `RESEND_API_KEY`) and a
Pages variable on the admin (`API_ORIGIN`).

## Agent tokens and binding an agent repo

An agent writes with a machine token: hashed in the database, scoped
(`resource:action`, e.g. `cases:write`), and always expiring (default 90
days, at most 365). Three ways to manage them. All show the plaintext only
once, and none can be reached with a machine token:

- **Admin UI:** the machine-tokens page: issue, see last use, revoke.
- **CLI:** `npm run mint-token -- --agent <name> --scope cases:write --days 90 --local|--remote`
  and `npm run revoke-token -- --id <id> | --agent <name> --local|--remote`.
- **CLI, on the agent's box:** when the agent runs on another machine, make
  the token there so the plaintext never leaves it:

  ```bash
  npm run mint-token -- --agent box-agent --scope todo:write --remote \
      --on ops@agent-box --token-file '~/.config/box-agent/admin-token'
  ```

  The token rules (`src/lib/token-rules.mjs`) run on the target over ssh
  stdin (`node` must be on its PATH, or give `--remote-node <path>`). The
  target writes the token to `--token-file` (mode 0600, directory 0700) and
  sends back only the id and the hash; this machine runs the INSERT. An
  existing token file is never overwritten. Quote a `~/` path so your shell
  does not expand it locally.
- **Bind an agent repo** (contract: `mentat.json` + `.mentat/local.json`),
  the only supported way to give an agent its admin:

  ```bash
  npm run connect -- --repo ~/code/my-agent --url http://localhost:8787 --local --plugins cases   # local admin (see Connect your agent)
  npm run connect -- --repo ~/code/my-agent --url https://admin.example.com --remote --plugins cases
  ```

  This mints a token for the agent named in the repo's `mentat.json`
  (`--agent` overrides; `--scope`, `--days`, `--token-env`, `--plugins` are
  optional) and writes, under the shared `.mentat/lock`:

  | file | what | committed? |
  |---|---|---|
  | `.env` | `MENTAT_ADMIN_TOKEN=<token>`, mode 0600 | no, must be gitignored |
  | `.mentat/local.json` | `admin: {url, token_env}` | no, must be gitignored |
  | `mentat.json` | `components.admin` | yes (no URL, no token) |

  It refuses, before minting anything, when `.env` or `.mentat/local.json`
  is not gitignored, when there is no `mentat.json` (the brain's installer
  creates it), when either file declares a newer `schema` than it knows, or
  when the URL is an IP address. Only its own keys are touched; unknown
  fields survive. The token itself is never printed.

## Export and restore

Everything this admin stores can leave as one JSON file and come back into a
fresh instance:

```bash
cd worker
npm run export -- --local --out ~/mentat-admin-export.json     # or --remote
npm run export -- --local --tables cases_case,cases_occurrence,cases_event   # one plugin's tables
npm run restore -- --local --in ~/mentat-admin-export.json --dry-run
npm run restore -- --local --in ~/mentat-admin-export.json
```

- The file holds every data table (users, agent token *hashes*, cases,
  plugin tables), written with mode 0600. Sign-in sessions and OTP codes are
  left out on purpose: they are short-lived credentials.
- Restore fills a **freshly migrated** instance: every table it writes must
  exist and be empty. It does not merge into live data. `--tables` leaves
  out what the target no longer has.
- `npm run migrate:local` / `migrate:remote` take a backup export into
  `config/backups/` (gitignored, like the instance file) **before** applying
  migrations, and stop if the export fails, so no schema change runs without a
  restorable copy.

## Set up your own instance (Cloudflare account)

**Scripted:** after `cd worker && npx wrangler login`, one command does
steps 2 to 8 below:

```bash
npm run instance:create -- --name acme --title "Acme Admin" \
    --admin-emails owner@acme.example,ops@acme.example --otp-sender admin@acme.example \
    [--location weur] [--account-id <id>] [--dry-run] [--resend-from-clipboard]
```

Names come from `--name`: D1 `mentat-admin-<name>`, worker
`mentat-admin-api-<name>`, Pages project `mentat-admin-<name>`. The instance
file lands in `~/.config/mentat-admin/<name>.json`; select it later with
`MENTAT_ADMIN_INSTANCE=<that file>`. Done steps are recorded next to it
(`<name>.state.json`), so after a failure rerun the same command and it
continues. `--dry-run` prints the steps and runs nothing. Secrets reach
wrangler only on stdin. The Resend API key stays the one manual step (the
command is printed at the end), unless `--resend-from-clipboard` pipes it
from `pbpaste`. Then, optionally, the todo principals:
`npm run instance:seed-principals -- --file principals.json --remote`
(shape: `{"humans":[{"email":"…","name":"…"}],"agents":[{"name":"<token label>"}]}`;
an agent needs a live `todo:write` token with that label; rerunning is safe).

**By hand:**

1. **Log in:** `cd worker && npx wrangler login`.
2. **D1 database:** `npx wrangler d1 create mentat-admin-db`, and note the
   `database_id` it prints.
3. **Instance file:** `mkdir -p ~/.config/mentat-admin && cp ../config/instance.example.json ~/.config/mentat-admin/instance.json`,
   then fill in: `title`, `cloudflare.account_id` (`npx wrangler whoami`),
   `worker.database_id`, `worker.vars` (`ALLOWED_ORIGINS` = your admin
   origin(s), `ADMIN_EMAILS` = who may sign in, `OTP_SENDER` = a mailbox on a
   domain verified in Resend, `SITE_URL` = linked in the mail footer), and
   `admin.pages_project`.
4. **Schema:** `npm run migrate:remote` (renders the config, applies
   `worker/migrations` to the remote D1).
5. **Worker secrets:**
   `npx wrangler secret put BETTER_AUTH_SECRET --config ../config/rendered/wrangler.toml`
   (a long random string), likewise `BETTER_AUTH_URL` (the public origin the
   admin is served from) and `RESEND_API_KEY`.
6. **Deploy the worker:** `npm run deploy`. Note its `*.workers.dev` URL.
7. **Pages project + API origin:** `npx wrangler pages project create <pages_project> --production-branch=main`,
   then `npx wrangler pages secret put API_ORIGIN --project-name=<pages_project>`
   with the worker URL from step 6.
8. **Deploy the admin:** `cd ../admin && npm run deploy` (render → build →
   `wrangler pages deploy`).
9. **Agent token** (optional): `cd ../worker && npm run connect -- --repo <agent-repo> --url <admin-url> --remote`
   (or `npm run mint-token -- --agent <name> --scope cases:write --remote`; see *Agent tokens* above).

The worker always deploys before the admin, because the admin calls the worker's API.

## Under the hood

Hono + D1 on Cloudflare Workers, Refine + Ant Design for the UI. The D1 test
emulator is in `worker/__tests__/helpers.ts`.
