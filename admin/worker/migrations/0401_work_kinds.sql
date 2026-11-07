-- Work kinds: a todo_task is a todo, a case or a backlog item. The kind is set at
-- creation and never changes; old workers keep running on the 'todo' default.
ALTER TABLE todo_task ADD COLUMN kind TEXT NOT NULL DEFAULT 'todo' CHECK (kind IN ('todo','case','item'));
CREATE INDEX todo_task_kind ON todo_task(kind, status, archived);

CREATE TABLE todo_case (
  task_id          TEXT PRIMARY KEY NOT NULL REFERENCES todo_task(id),
  goal             TEXT,     -- what "done" means for the whole case
  frame            TEXT,     -- scope, limits, mandate, what not to do
  next_action      TEXT,     -- the next concrete step the ball holder takes
  waiting_on       TEXT,     -- someone outside the system the case waits for
  due_reason       TEXT,     -- why the due date is what it is
  brain_ref        TEXT,     -- path of the case markdown in the agent's brain
  review_every     INTEGER CHECK (review_every IS NULL OR review_every > 0),  -- days; NULL = not monitored
  last_reviewed_at TEXT, last_reviewed_by TEXT REFERENCES todo_principal(id),
  confirmed_at     TEXT, confirmed_by TEXT REFERENCES todo_principal(id)      -- NULL = an agent's proposal
);

ALTER TABLE todo_principal ADD COLUMN about TEXT;

-- Provenance of imported comments; the actor (author_id) is the importer principal.
ALTER TABLE todo_comment ADD COLUMN source_system TEXT;
ALTER TABLE todo_comment ADD COLUMN source_id TEXT;
ALTER TABLE todo_comment ADD COLUMN source_author TEXT;
ALTER TABLE todo_comment ADD COLUMN source_created_at TEXT;
CREATE UNIQUE INDEX todo_comment_source ON todo_comment(source_system, source_id) WHERE source_id IS NOT NULL;
