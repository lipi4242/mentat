# Cases and backlog items

Todos, cases and backlog items live in one store under `/api/todo/v1`, with
the same auth, comments, labels, deps, mentions and `/changes` feed. A task's
`kind` (`todo`, `case`, `item`) is set when it is created and never changes.

Every write takes `expected_rev` (the task's current `rev`); every create
takes `idem_key`. Errors are `{error}`: 403 for the wrong caller, 404 for an
unknown id, 409 for a stale revision or a step that is not allowed from the
current state (the body then also has `current`, with `stage` and `rev` for an
item), and 422 for invalid input. Principals may be named by id or handle.
The actor is always the caller's own principal; no field names another one.

## Cases

A case is a one-off process with a goal and a frame. Its todos are its children.

| Route | Body / filters |
|---|---|
| `POST /tasks` | `kind:'case'` plus `case:{goal,frame,next_action,waiting_on,due_reason,brain_ref,review_every}`. A case has no parent and no `repeat_rule` (recurring obligations stay in the cases plugin). A human's case is confirmed at once; an agent's case is a proposal |
| `PATCH /tasks/:id` | `{set?, case?, expected_rev}` |
| `GET /tasks/:id` | a case also returns its `case` fields |
| `POST /tasks/:id/review` | `{note?, expected_rev}`; owner or assignee; stamps `last_reviewed_at/by` |
| `POST /tasks/:id/confirm` | `{expected_rev}`; humans only; an already confirmed case is returned unchanged |
| `GET /cases/review-due` | `for=<handle>` (optional): open, confirmed cases with `review_every` whose last review (or creation) is at least that many days ago, most overdue first |
| `POST /tasks/:id/complete` | open descendants → 409 `{open_children}` unless `children:'close'` (completes the open todos in the same write) or `children:'keep'` |

## Backlog items

An item belongs to a project and has a key such as `APP-12`. Its PM is the
task's `owner_id`; its developer is `dev_id`. The ball is
`coalesce(assignee_id, owner_id)`. Generic task writes (`PATCH /tasks`,
`complete`, `handback`) are refused on an item; `move`, comments, labels and
deps work as for any task. `GET /tasks` leaves items out unless `kind` asks.

| Route | Who | Body / filters |
|---|---|---|
| `GET /projects` | any | |
| `POST /projects` | human or importer | `{prefix, name, default_pm?, idem_key}`; prefix is 1–8 of `A–Z0–9`, starts with a letter, never changes |
| `POST /items` | any | `{project, title, description?, priority?, estimate?, pm?, parent?, request_quote?, request_ref?, acs?:[text], idem_key}`; `project` is an id or prefix; PM = `pm`, else the project's default PM, else the caller; `parent` must be an item of the same project |
| `GET /items` | any | `project=`, `stage=` (comma list), `pm=`, `dev=`, `ball=` (handles), `older_than=<days>` (no change for that long; an `issued` item counts from its issue); ranked by `position` |
| `GET /items/:ref` | any | `ref` is an id or `PREFIX-N` (any case). Returns the item with `acs`, `links`, `reports` (each with `results`), `children`, `comments`, `labels`, `deps`, `events` |
| `PATCH /items/:id` | PM | `{set:{title,description,priority,estimate,pm,request_quote,request_ref}, expected_rev}` |
| `POST /items/:id/acs` | PM | `{text, expected_rev}` |
| `PATCH /acs/:id` | PM | `{text, expected_rev}` (the item's rev) |
| `POST /acs/:id/remove` | PM | `{expected_rev}`; ACs are never deleted |
| `POST /items/:id/links` | PM or dev | `{kind:'pr'\|'issue'\|'url', url, title?}` or `{kind:'task', task_id}`, plus `expected_rev`; a live duplicate is 422 |
| `POST /links/:id/remove` | PM or dev | `{expected_rev}` |

AC changes are allowed only while the item is `draft`, `issued` or `taken`.
An item has at most 200 live ACs (create, add and import alike).
A human admin may do anything a PM may; developer steps belong to the
developer only. `priority` is 0 (none), 1 (urgent) … 4 (low).

### Steps

`POST /items/:id/<step>` with `expected_rev`:

| Step | From | Who | To | Ball after | Body |
|---|---|---|---|---|---|
| `issue` | draft | PM | issued | dev | `{dev, note?}`; needs ≥1 live AC |
| `take` | issued | dev | taken | dev | `{note?}` |
| `handback` | issued, taken | dev | draft | PM | `{note}` (required); clears `dev_id` |
| `submit` | taken | dev | review | PM | `{round, results, summary, body?, head_sha?, links?:[{kind?:'pr',url,title?}]}` |
| `accept` | review | PM | done | — | `{checks, note?}` |
| `reject` | review | PM | taken | dev | `{checks, note}` |
| `hold` | draft, issued, taken, review | PM | hold | PM | `{note?}`; remembers `hold_from` |
| `resume` | hold | PM | `hold_from` | dev if issued/taken, else PM | `{note?}` |
| `drop` | any but done/dropped | PM | dropped | — | `{note?}` |

`done` and `dropped` are final. Notes are kept in the item's `events`.

- `submit.round` is the last round + 1; a replayed form is a 409.
- `submit.results` is `[{ac_id, verdict, evidence}]` with **exactly** the
  item's live AC ids, once each. `verdict` is `met`, `not_met` or `na`.
  A `not_met` is accepted here; the PM decides.
- `checks` is `[{ac_id, pm_ok, pm_note?}]` covering every result of the
  current round once; `pm_ok` is `true`/`false` (`1`/`0` also accepted).
- `submit` needs at least one live AC.
- `accept` needs every `pm_ok` true and every verdict `met` or `na`, and the
  report must cover every live AC (otherwise 409: reject, and the developer
  reports again).
- `reject` needs at least one `pm_ok:false`, a `pm_note` on each of those,
  and a `note`.
- `pm_ok` and `pm_note` are written only by `accept` and `reject`.

## Linear import

For the importer (`anytime_todo import-linear`). It needs a human session or
an agent token with the scopes `todo:write todo:import`. No token has
`todo:import` unless it is granted explicitly; a plain agent token gets 403.

| Route | Body |
|---|---|
| `POST /items/import` | `{ext_ref, project, number, title, description?, priority?, estimate?, stage, dev?, archived?, created_at?, labels?:[name], acs?:[{source_id,text}], comments?:[{source_system,source_id,body,source_author?,source_created_at?}], links?:[{url,title?}], idem_key?}` → `{id, key, created, added:{acs,comments,labels,links}, skipped:{acs}}` |
| `POST /items/import/parent` | `{ext_ref, parent_ext_ref}`; sets the parent only if the item has none |

The item keeps its Linear number (`APP-431` stays `APP-431`), and the
project's next number moves past it. `stage` is `draft`, `taken` (needs
`dev`), `done` or `dropped`. A rerun with the same `ext_ref` adds only the
missing comments and PR links, and missing ACs while the item is `draft`,
`issued` or `taken` (later ones are counted in `skipped.acs`). Labels come
only with a new item. A rerun never changes anything edited in Mentat. A number already used by an item created in Mentat is a 409.

## Contract: differences from the design spec

These are the points where the API differs from, or adds to, the design spec (§2 of the backlog SPEC).
Clients should follow this file.

1. **Status codes.** Invalid input is **422**, not 400. 403: wrong caller.
   404: unknown id or key. 409: stale `expected_rev`, a step not allowed from
   the current stage, a replayed `submit` round, an AC change outside
   draft/issued/taken, an import number taken by a native item, or a case with
   open children. A 409 body is `{error, current}`; for an item, `current` is
   the full item row including `stage` and `rev`. A case-completion 409 also
   has `open_children:[id]`.
2. **Import endpoints (new).** `POST /items/import` and
   `POST /items/import/parent`, as described above. They and `POST /projects`
   accept a human session or a token with `todo:write todo:import`. No token
   has `todo:import` by default.
3. **Principal references.** `pm`, `dev`, `default_pm` and the import `dev`
   accept a principal id or a handle. Query filters (`ball=`, `owner=`,
   `assignee=`, `pm=`, `dev=`, `for=`) take a handle; an unknown handle is 422.
4. **`checks`.** `[{ac_id, pm_ok, pm_note?}]`, `pm_ok` is `true`/`false` or
   `1`/`0`. For both `accept` and `reject` it must name every result of the
   current round exactly once. `reject` also needs a `pm_note` on each
   `pm_ok:false` and a `note`.
5. **`handback`** clears `dev_id`; the next `issue` names a developer again.
6. **`older_than=<days>`** on `GET /items` compares with `updated_at` (no
   change for that many days); for an `issued` item it compares with
   `issued_at`, so a comment does not hide an item nobody has taken.
7. **Item detail** (`GET /items/:ref`) also returns `key`, `events` (the
   item's event log, where step notes live), `labels` and `deps`. There is no
   current-round field: the next `submit.round` is `reports.length + 1`.
8. **Steps take an id only.** `/items/:id/<step>`, `PATCH /items/:id`,
   `/items/:id/acs` and `/items/:id/links` take the ULID; only
   `GET /items/:ref` resolves `PREFIX-N`.
9. **Cases in reads.** `GET /tasks/:id` adds `case:{goal, frame, next_action,
   waiting_on, due_reason, brain_ref, review_every, last_reviewed_at,
   last_reviewed_by, confirmed_at, confirmed_by}`. `GET /tasks` rows do not
   carry case fields. `GET /cases/review-due` returns task rows with the case
   fields flattened onto them, plus `overdue_days`; `for` is optional.
10. **Notes.** `note` is optional on `issue`, `take`, `hold`, `resume`,
    `drop` and `review`; required on `handback` and `reject`.
11. **Submit links.** `links:[{kind?:'pr', url, title?}]`; they become `pr`
    links, deduplicated against the item's live links.
12. **Mentions in AC text and reports.** `@handle` in AC text, `summary` or
    `body` adds the principal to the event's recipients; it is not stored as
    a mention row.
13. **Principals.** `POST /principals` accepts `about` (text, up to 500).
    `GET /me` returns the caller's principal row.
14. **Event kinds.** Item steps write `item_<step>` (`item_issue`,
    `item_submit`, …). Other new kinds: `item_updated`, `ac_added`,
    `ac_edited`, `ac_removed`, `link_added`, `link_removed`, `case_reviewed`,
    `case_confirmed`, `project_created`, `imported`, `import_filled`. Closing
    a case's children writes one `completed` event per child.
15. **Responses.** Every write on an item returns the item row (anchor fields
    plus `project_id, number, stage, priority, estimate, dev_id, hold_from,
    request_quote, request_ref, issued_at, taken_at, ext_ref, key`); creates
    are 201 and replays 200. Case writes return the task with `case:{…}`.
