-- Backlog items: an item is a todo_task with kind = 'item' plus this 1:1 extension.
CREATE TABLE backlog_project (
  id TEXT PRIMARY KEY NOT NULL,
  prefix TEXT NOT NULL UNIQUE CHECK (prefix GLOB '[A-Z]*' AND prefix NOT GLOB '*[^A-Z0-9]*' AND length(prefix) <= 8),
  name TEXT NOT NULL,
  default_pm_id TEXT REFERENCES todo_principal(id),
  next_number INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL REFERENCES todo_principal(id), idem_key TEXT NOT NULL,
  UNIQUE(created_by, idem_key)
);
-- The prefix is immutable (no endpoint changes it), so a key never changes meaning.

CREATE TABLE backlog_item (
  task_id    TEXT PRIMARY KEY NOT NULL REFERENCES todo_task(id),
  project_id TEXT NOT NULL REFERENCES backlog_project(id),
  number     INTEGER NOT NULL,
  stage      TEXT NOT NULL DEFAULT 'draft'
             CHECK (stage IN ('draft','issued','taken','review','done','hold','dropped')),
  priority   INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 4),  -- 0 none, 1 urgent … 4 low
  estimate   INTEGER CHECK (estimate IS NULL OR estimate >= 0),
  dev_id     TEXT REFERENCES todo_principal(id),
  hold_from  TEXT CHECK (hold_from IS NULL OR hold_from IN ('draft','issued','taken','review')),
  request_quote TEXT, request_ref TEXT,          -- the requester's exact words, and where they said them
  issued_at TEXT, taken_at TEXT,                 -- issue and take receipts
  ext_ref    TEXT,                               -- 'linear:<uuid>' for imported items
  UNIQUE(project_id, number),
  CHECK ((stage = 'hold') = (hold_from IS NOT NULL))
);
CREATE UNIQUE INDEX backlog_item_ext ON backlog_item(ext_ref) WHERE ext_ref IS NOT NULL;
CREATE INDEX backlog_item_stage ON backlog_item(project_id, stage);

CREATE TABLE backlog_ac (
  id TEXT PRIMARY KEY NOT NULL, item_id TEXT NOT NULL REFERENCES backlog_item(task_id),
  position TEXT NOT NULL, text TEXT NOT NULL CHECK (length(trim(text)) > 0),
  created_by TEXT NOT NULL REFERENCES todo_principal(id), created_at TEXT NOT NULL,
  removed_at TEXT,                               -- never deleted
  source_id TEXT                                 -- 'linear:<uuid>:ac:<n>' for imported ACs
);
CREATE UNIQUE INDEX backlog_ac_source ON backlog_ac(source_id) WHERE source_id IS NOT NULL;

CREATE TABLE backlog_report (
  id TEXT PRIMARY KEY NOT NULL, item_id TEXT NOT NULL REFERENCES backlog_item(task_id),
  round INTEGER NOT NULL, submitted_by TEXT NOT NULL REFERENCES todo_principal(id), submitted_at TEXT NOT NULL,
  head_sha TEXT, summary TEXT NOT NULL, body TEXT,
  pm_verdict TEXT CHECK (pm_verdict IN ('accepted','rejected')), pm_note TEXT,
  decided_by TEXT REFERENCES todo_principal(id), decided_at TEXT,
  UNIQUE(item_id, round)
);

CREATE TABLE backlog_ac_result (
  report_id TEXT NOT NULL REFERENCES backlog_report(id),
  ac_id     TEXT NOT NULL REFERENCES backlog_ac(id),
  ac_text   TEXT NOT NULL,                       -- snapshot of the AC as it was at submit
  verdict   TEXT NOT NULL CHECK (verdict IN ('met','not_met','na')),
  evidence  TEXT NOT NULL CHECK (length(trim(evidence)) > 0),
  pm_ok     INTEGER CHECK (pm_ok IN (0,1)), pm_note TEXT,   -- written only by accept/reject
  PRIMARY KEY(report_id, ac_id)
);

CREATE TABLE backlog_link (
  id TEXT PRIMARY KEY NOT NULL, item_id TEXT NOT NULL REFERENCES backlog_item(task_id),
  kind TEXT NOT NULL CHECK (kind IN ('pr','issue','url','task')),
  url TEXT, task_id TEXT REFERENCES todo_task(id), title TEXT,
  created_by TEXT NOT NULL REFERENCES todo_principal(id), created_at TEXT NOT NULL, removed_at TEXT,
  CHECK ((kind = 'task') = (task_id IS NOT NULL)), CHECK ((kind = 'task') = (url IS NULL))
);
CREATE UNIQUE INDEX backlog_link_url  ON backlog_link(item_id, kind, url) WHERE kind <> 'task' AND removed_at IS NULL;
CREATE UNIQUE INDEX backlog_link_task ON backlog_link(item_id, task_id)  WHERE kind = 'task'  AND removed_at IS NULL;
