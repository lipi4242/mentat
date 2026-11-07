# mentat.json — component manifest and synergy matrix

Schema 1. [Magyarul](mentat-json.hu.md)

The four building blocks — **brain** (the repository root), **engine**
(`engine/`), **fleet** (`fleet/`) and **admin** (`admin/`), all in the one Mentat
repository — each work on their own. Two files in the agent's repo tie them together:

- **`mentat.json`** (committed): INTENT — which elements belong to the agent
  and their paths inside the repo. No machine, version or endpoint facts.
- **`.mentat/local.json`** (git-ignored): FACT on this machine — installed
  versions, the fleet identity, the admin endpoint. It does not travel with a
  clone, so a clone never claims something that is not true.

## 1. Shape

```json
// mentat.json
{
  "schema": 1,
  "agent": { "name": "my-agent", "language": "en" },
  "components": {
    "brain":  { "root": "brain" },
    "engine": { "path": "anytime_engine", "plugins": ["agent.concerns"], "schedule_owner": "engine" },
    "fleet":  {},
    "admin":  { "plugins": ["cases"] }
  },
  "cases": { "backend": "markdown" },
  "roles": { "default": "asszisztens", "installed": ["asszisztens", "fejleszto"] }
}
// .mentat/local.json
{
  "schema": 1,
  "installed": { "brain": "0.2.0", "engine": "0.3.0", "fleet": "1.1.0" },
  "fleet": { "agent_id": "my-agent", "host": "my-box" },
  "admin": { "url": "http://localhost:8787", "token_env": "MENTAT_ADMIN_TOKEN" }
}
```

## 2. Rules

1. **Key owners.** `schema`, `agent` and `roles`: the brain installer. `components.<x>`
   and `installed.<x>`: element x's installer. `cases`: the `cases` CLI (the
   brain installer only *seeds* `cases.backend: markdown` when it is missing).
   `fleet` in local: the fleet; `admin` in local: the admin connection. Nobody
   touches another owner's key. **The one exception:**
   `components.engine.schedule_owner` may also be written by the fleet's join
   (`engine` → `fleet`), per rule 5; it touches no other engine key. The first
   writer of a file creates it with `"schema": 1`.
2. **Write under a lock.** Every writer holds an exclusive `flock` on
   `.mentat/lock` around the whole read → merge own key (unknown fields of the
   own section are kept) → write temp file + rename. Key order is not part of
   the contract.
3. **Trust boundary.** The committed file carries no endpoint and loads no
   code: paths are relative and inside the repo (`..` and absolute paths are
   refused); `plugins` are dotted package names of the repo itself, never URLs
   or paths. The admin URL and the token's env-var name live in the local
   file; the token itself in `.env` (0600, git-ignored). Hostnames yes, IP
   addresses no. All three are written only by the admin's `npm run connect`
   (`--local` for an admin on this machine) — never by hand; a session looks
   for the admin nowhere else.
4. **A missing element is absent, and an optional synergy quietly stays off**
   — but `status` says so ("admin: not connected"). **Exception: an explicitly
   chosen data store.** If `cases.backend` is `admin` and the admin is missing
   or unreachable, case operations stop with an error — there is no fallback
   to markdown. Switching backend only through `cases migrate`.
5. **One schedule owner.** `engine.schedule_owner` is `engine` (the engine's
   own timer) or `fleet`. The fleet's join takes it over idempotently; the
   engine refuses to install its timer while the owner is `fleet`.
6. **Unknown `schema` (greater than known) → diagnostics only**: start no
   task, write neither the files nor the admin. A new field is non-breaking
   only if ignoring it still gives correct behaviour; otherwise `schema` grows.
7. **Unknown keys are tolerated**; a reader never fails on them.
8. **Roles.** `roles.installed` lists role names (`^[a-z][a-z0-9-]*$`) and
   `roles.default` must be one of them; otherwise the reader reports
   `invalid_value` (at `roles.default` or `roles.installed[i]`) without
   disabling any element. A role applies to a run, not to the repo: the
   effective role is `MENTAT_ROLE` if installed (else an error), otherwise
   `roles.default`, switched in a session with `/szerep`. Permissions are
   enforced by the role-guard hook, not by this file (see
   `bekotes/BEKOTES.en.md`).

**Present** means: declared in `mentat.json` `components`, installed here
(`installed.<x>` in local; for the admin: `admin.url`), and without errors in
its own section. An element with an invalid entry is treated as absent.

## 3. Synergy matrix

| pair | what turns on | implemented by |
|---|---|---|
| brain + engine | engine providers read from the brain `root` (todos, cases, decisions); starter concern: morning review | engine |
| brain + fleet | the join checks that CLAUDE.md loads AGENTS.md | fleet |
| engine + fleet | the fleet owns the tick schedule (rules 2, 5) and watches `last-tick.json` | fleet |
| brain + admin | only with `cases.backend: admin`: cases live in the admin, brain files point to them with `brain_ref` | admin `cases` CLI |
| engine + admin | a `cases.due` provider reads the admin API | engine concern package |
| fleet + admin | fleet plugin: desired and observed state | fleet + admin |

Every element ships a `status` command that prints what it sees in the two
files and which synergies are live. The brain's is the [`status` skill](../skills/status/SKILL.en.md).

## 4. release.json

Every release publishes one `release.json` at the root of the tagged tree, so the
metadata belongs to the release you install:

```json
{
  "component": "mentat", "version": "0.5.0", "date": "2026-11-05",
  "severity": "minor", "security": false, "breaking": true,
  "migrations_from": ["0.4"],
  "you_need_to": ["Re-sync the engine from the one clone: ~/src/mentat/engine/sync-to.sh <your-repo>"],
  "changelog": "CHANGELOG.md#050",
  "requires_if_present": { "engine": ">=0.5.0,<0.6" },
  "components": { "engine": "0.5.0", "bridge": "2.0.1", "plugin": "1.6.0" }
}
```

- `severity`: `patch | minor | major`; `security` is a separate flag.
- When skipping versions, the updater reads the intermediate `release.json`
  files in order; `migrations_from` says which versions have a direct path.
- `components` lists the internal version of each part shipped in the release
  (the engine follows the product version; the bridge and the plugin keep
  their own numbers).
- `requires_if_present` applies only when the other element is present.
  Format: `MAJOR.MINOR[.PATCH]` with comma-separated `>=` and `<`. There is no
  resolver: on a conflict the updater stops and says so.

## 5. Reference implementation and conformance

[`manifest/`](manifest/) holds the canonical copy: `mentat_manifest.py`
(`load`, `local`, `present`, `update` with the rule-2 lock, `evaluate_root`),
`mentat_rules.py` (pure validation and synergies), `mentat_roles.py` (roles
check and the `roles` / `role` commands), `mentat_cli.py` (`init-brain`,
`status`). Stdlib only; Python elements vendor the three library files. `manifest/conformance/*.json` are the shared fixtures — input files and
the expected result — that every reader, including the TypeScript admin, must
pass. Error codes: `unreadable`, `schema_unknown`, `path_outside_repo`,
`plugin_invalid`, `endpoint_in_manifest`, `ip_address`, `invalid_value`,
`cases_backend_unavailable`.

```bash
python3 -m unittest discover -s reference/manifest
```
