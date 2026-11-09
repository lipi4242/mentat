# Todo — installation and agent API

Todo tracks a shared task tree, assignments, checklists, labels and comments.
Completing a recurring task advances the same row beyond today; missed dates
never create backlog. Dropped work is a valid closure.

## Install and identify callers

1. The product registries are `config/plugins.ts` and `admin/src/instance.ts`.
   Todo owns migration band **0400–0499**. For a dedicated todo instance,
   select only `todoPlugin` / `todoUI` in those registries. Ship
   `0400_todo.sql` separately through the human-approved migration track;
   after the owner applies it, release worker first, then admin. Do not run
   migrations as part of a code deploy.
2. Sign in as an allowlisted admin. On **Résztvevők**, create a human principal
   with your login email, a lowercase handle (`[a-z0-9_]+`) and display name.
   This self-bootstrap works before any principal exists. Other API routes
   require a mapped, enabled principal.
3. In **Gépi tokenek**, issue a token with **`todo:write`** (this scope also
   permits reads). On **Résztvevők**, create an agent principal with that
   token's **id**, not its plaintext value. One token maps to one principal.
   Include its Telegram bot photo as `avatar` using **Agent avatar at token setup** below.
   Tokens remain core credentials: expiry/revocation takes effect immediately.
4. Store the plaintext token only in the agent's existing secret store or a
   gitignored, mode-0600 environment file. Set `MENTAT_TOKEN` from there;
   do not paste tokens into chat, commits or curl command history. Record the
   instance URL and `todo` in the agent repo's Mentat configuration. No brain
   inventory is migrated automatically.

All routes below are under `/api/todo/v1`. The token header is
`X-Mentat-Token`, not Authorization. A supplied token header (even an empty
one) takes precedence over cookies. Authentication is the shared guard of every
plugin (`lib/guards.ts`): unknown, expired or revoked tokens and missing browser
authentication return 401; a live token without `todo:write` returns 403, and
so does a token or session with no live principal mapped to it. Principals can only be created
by an admin session. Agents create tasks directly. Everyone sees all tasks in
this shared instance; there is no per-list scoping or task-level ACL in the MVP.

## Agent avatar at token setup

Owner decision (2026-10-27): use the agent's Telegram **bot profile photo**.
Fetch it on the agent host when setting up its token/principal (step 3 above):

1. With the bot token from the agent's secret store, call Telegram `getMe` and
   take `result.id` as the bot user ID.
2. Call [`getUserProfilePhotos`](https://core.telegram.org/bots/api#getuserprofilephotos)
   with `user_id=<bot-id>&limit=1`; choose a small size from `result.photos[0]`
   and take its `file_id`. If no photo exists, set the bot's profile photo first.
3. Call [`getFile`](https://core.telegram.org/bots/api#getfile) with that
   `file_id`, then download `https://api.telegram.org/file/bot<TOKEN>/<file_path>`
   using the returned `result.file_path`, on the agent host only.
4. Base64-encode the image bytes as `data:image/jpeg;base64,...` (use the actual
   PNG/JPEG/WebP/GIF MIME type). The complete URI must fit 65,536 bytes; select
   a smaller size or resize locally if necessary.
5. During admin-session `POST /principals`, include that URI in `avatar` together
   with `kind: "agent"` and `agent_token_id`, or paste it into the **Résztvevők**
   avatar field. It is stored in `todo_principal.avatar` and shown by the UI.

Only image data is sent to Mentat. Never store the Telegram token or the
Telegram download URL in the worker or avatar field. Principal creation is
idempotent and create-only: replaying its key does not update an existing avatar.

## Agent examples

Assumes `jq`, `MENTAT_URL` (worker origin), and a securely loaded
`MENTAT_TOKEN`. Persist the create key before the first request and reuse it
until that request succeeds. First payload wins; a replay returns 200 and
creates no extra event.

```sh
TODO_API="$MENTAT_URL/api/todo/v1"
# Example stable key: replace for each new logical task, retain for retries.
TASK_JSON=$(curl --fail-with-body -sS "$TODO_API/tasks" \
  -H "X-Mentat-Token: $MENTAT_TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Reggeli check-in","repeat_rule":"weekdays","due_date":"2026-10-28","idem_key":"morning-check-in-v1"}')
TASK_ID=$(printf '%s' "$TASK_JSON" | jq -r '.id')
REV=$(printf '%s' "$TASK_JSON" | jq -r '.rev')

# Make a child; owner defaults to the calling principal.
curl --fail-with-body -sS "$TODO_API/tasks" \
  -H "X-Mentat-Token: $MENTAT_TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg p "$TASK_ID" '{title:"Egy kis lépés",parent_id:$p,idem_key:"morning-child-v1"}')"

# Every task mutation, including comments/labels/deps, needs its current rev.
curl --fail-with-body -sS -X PATCH "$TODO_API/tasks/$TASK_ID" \
  -H "X-Mentat-Token: $MENTAT_TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -n --argjson r "$REV" '{expected_rev:$r,set:{description:"@owner Egy közös lépés"}}')"

# Read back before a different write; never blindly refresh rev to retry complete.
TASK_JSON=$(curl --fail-with-body -sS "$TODO_API/tasks/$TASK_ID" -H "X-Mentat-Token: $MENTAT_TOKEN")
REV=$(printf '%s' "$TASK_JSON" | jq -r '.rev')
curl --fail-with-body -sS "$TODO_API/tasks/$TASK_ID/complete" \
  -H "X-Mentat-Token: $MENTAT_TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -n --argjson r "$REV" '{expected_rev:$r}')"

# Change feed: persist the last processed seq, follow pages until empty.
curl --fail-with-body -sS "$TODO_API/changes?since=0&limit=100&for=my_agent" \
  -H "X-Mentat-Token: $MENTAT_TOKEN"
```

On **409**, `{error,current}` contains the current task. Inspect it and
reconcile intent before another write. A lost complete response must be
retried with the original revision, so it cannot complete the next occurrence.
Validation errors are 422 `{error}`. Dates are `YYYY-MM-DD`; `due_time` is
`HH:MM` in the task's IANA timezone and requires `due_date`.

| Route | Body / filters |
|---|---|
| `GET /tasks` | `parent=<id>` or `root=1`, `ball=<handle>`, `owner=<handle>`, `assignee=<handle>` (empty `assignee=` means unassigned), `label=<label-id>`, `status=`, `due_before=`, `kind=todo\|case\|item` (comma list or `all`; default `todo,case`); unknown handles are 422; filters combine with AND; no filters returns every todo and case as flat rows |
| `GET /tasks/:id` | task plus immediate `children`, `labels`, `comments`, `deps` |
| `POST /tasks` | fields, required `title` + `idem_key`; optional `parent_id`, `position` |
| `PATCH /tasks/:id` | `{set,expected_rev}`; use complete for done and move for parent/position |
| `POST /tasks/:id/move` | `{parent_id,position?,expected_rev}`; null parent = root |
| `POST /tasks/:id/complete` | `{expected_rev}` |
| `POST /tasks/:id/handback` | `{expected_rev,note?}`; current assignee only |
| `POST /tasks/:id/comments` | `{body,expected_rev}`; append-only |
| `POST /tasks/:id/labels` | `{label_ids,expected_rev}`; replaces the set |
| `POST /tasks/:id/deps` | `{depends_on_id,remove?,expected_rev}`; rejects cycles |
| `GET /labels`, `POST /labels` | create `{name,color?,idem_key}`, color `#RRGGBB` |
| `GET /principals`, `POST /principals` | create `{kind,handle,display_name,auth_email?,agent_token_id?,avatar?,idem_key}`; admin session only for POST |
| `GET /me` | the caller's own principal |
| cases, backlog items | see [BACKLOG.md](BACKLOG.md) |
| `GET /changes` | `since` exclusive seq, `limit` 1–500, optional known `for=<handle>`; ascending array, `diff_json` and `recipients_json` are JSON strings |

Design decisions: parents close separately.
Completing a parent leaves open children unchanged; finishing all children does
not close the parent. Both task GET routes return server-computed `progress`
(`{done,total,percent}`, or `null` for leaves), including detail's children.
Each descendant leaf has equal weight, dropped branches are excluded, and
archived leaves count. Internal task status does not override its leaves.
Percent is rounded to a whole number; a parent with only dropped branches has
`{done:0,total:0,percent:0}`. Filters do not change these counts. The UI shows a
small neutral indicator in the tree and detail. Planned-date ETA is future work.
An assignee can complete the whole task or hand back only their step. Recurrence
rolls the same row forward; occurrence history lives only in the event log.

## Agent polling

No reminders in the MVP: no reminder fields, endpoints, or delivery service.
Agents run their own schedule (for example, Thufir hourly plus a morning run):

1. Read `GET /changes?since=<saved-seq>&for=<handle>&limit=100`. Process in seq
   order, persist the last successfully processed seq, and page until empty.
   Keep a separate cursor for each feed/filter; deduplicate retried events by seq.
2. Read `GET /tasks?ball=<handle>&due_before=YYYY-MM-DD&status=open` for work
   whose ball is with the agent (assignee, otherwise owner). `ball` resolves a
   known handle, not a principal ID; unknown handles return 422. The date cutoff
   is inclusive; undated tasks are omitted. Skip archived rows locally.
3. Act using the agent's own context. Fetch the current revision before writes;
   use stable create keys and expected_rev as above. The worker does not schedule
   or send notifications. Agents own their cursor, schedule, and any delivery.

## Recurrence

Rules: `daily`, `weekdays`, `weekly:mon,wed,fri`, `every:N:days`,
`every:N:weeks`, `monthly:15`, `monthly:last`, `monthly:2:tue`, `yearly:03-14`.
N is 1–3660; monthly ordinal is 1–5 (missing fifth weekdays skip that month).
Month-end dates clamp. `repeat_from` is `schedule` (default) or `completion`;
calendar patterns retain their calendar meaning in either mode. Rollover
reopens completed descendants, preserving dropped/archived branches and
children's own schedules. Mentions match active handles in raw markdown;
unknown handles are ignored. Inbox recipients are retained as of each event.
