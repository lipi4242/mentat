-- Todo owns 0400–0499. Core credential mappings are checked by the API.
CREATE TABLE todo_principal (
  id TEXT PRIMARY KEY NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('human','agent')),
  handle TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  avatar TEXT,
  auth_email TEXT UNIQUE,
  agent_token_id TEXT UNIQUE,
  created_by TEXT NOT NULL,
  idem_key TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  disabled_at TEXT,
  UNIQUE(created_by, idem_key),
  CHECK ((kind = 'human' AND auth_email IS NOT NULL AND agent_token_id IS NULL)
      OR (kind = 'agent' AND agent_token_id IS NOT NULL AND auth_email IS NULL))
);
CREATE TABLE todo_task (
  id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 26),
  parent_id TEXT REFERENCES todo_task(id),
  position TEXT NOT NULL,
  title TEXT NOT NULL CHECK (length(trim(title)) > 0),
  description TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','dropped')),
  due_date TEXT, due_time TEXT, planned_date TEXT,
  tz TEXT NOT NULL DEFAULT 'Europe/Budapest',
  owner_id TEXT NOT NULL REFERENCES todo_principal(id),
  assignee_id TEXT REFERENCES todo_principal(id), assignee_note TEXT,
  repeat_rule TEXT,
  repeat_from TEXT NOT NULL DEFAULT 'schedule' CHECK (repeat_from IN ('schedule','completion')),
  idem_key TEXT NOT NULL, rev INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES todo_principal(id),
  updated_at TEXT NOT NULL, updated_by TEXT NOT NULL REFERENCES todo_principal(id),
  done_at TEXT, done_by TEXT REFERENCES todo_principal(id),
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  UNIQUE(created_by, idem_key),
  CHECK (repeat_rule IS NULL OR due_date IS NOT NULL),
  CHECK (due_time IS NULL OR due_date IS NOT NULL)
);
CREATE INDEX todo_task_parent ON todo_task(parent_id, position, id);
CREATE INDEX todo_task_due ON todo_task(status, archived, due_date);
CREATE TABLE todo_label (
  id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE, color TEXT,
  created_by TEXT NOT NULL REFERENCES todo_principal(id), idem_key TEXT NOT NULL,
  UNIQUE(created_by, idem_key)
);
CREATE TABLE todo_task_label (
  task_id TEXT NOT NULL REFERENCES todo_task(id),
  label_id TEXT NOT NULL REFERENCES todo_label(id), PRIMARY KEY(task_id,label_id)
);
CREATE TABLE todo_dep (
  task_id TEXT NOT NULL REFERENCES todo_task(id),
  depends_on_id TEXT NOT NULL REFERENCES todo_task(id), PRIMARY KEY(task_id,depends_on_id),
  CHECK (task_id <> depends_on_id)
);
CREATE TABLE todo_comment (
  id TEXT PRIMARY KEY NOT NULL, task_id TEXT NOT NULL REFERENCES todo_task(id),
  author_id TEXT NOT NULL REFERENCES todo_principal(id), body TEXT NOT NULL,
  created_at TEXT NOT NULL, edited_at TEXT
);
CREATE INDEX todo_comment_task ON todo_comment(task_id, created_at);
CREATE TABLE todo_mention (
  source_kind TEXT NOT NULL CHECK (source_kind IN ('task','comment')),
  source_id TEXT NOT NULL, principal_id TEXT NOT NULL REFERENCES todo_principal(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY(source_kind, source_id, principal_id)
);
CREATE TABLE todo_event (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  op_id TEXT NOT NULL UNIQUE,
  task_id TEXT REFERENCES todo_task(id), at TEXT NOT NULL,
  actor_id TEXT NOT NULL REFERENCES todo_principal(id), kind TEXT NOT NULL,
  diff_json TEXT NOT NULL CHECK (json_valid(diff_json)),
  recipients_json TEXT NOT NULL CHECK (json_valid(recipients_json))
);
CREATE INDEX todo_event_task ON todo_event(task_id,seq);
