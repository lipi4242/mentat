-- Mentat Admin core: cases, their event trail, and machine (agent) tokens.
--
-- Timestamps: these tables deliberately use datetime('now') TEXT timestamps
-- (readable, human-diffable), while the better-auth tables in 0001_auth.sql
-- use INTEGER epoch-ms (that's better-auth's own convention). Both are fine
-- in isolation, but they are NOT directly comparable — to correlate a
-- case_event.at (or case.created_at/updated_at) with an auth_session/
-- auth_user timestamp, convert one side: unixepoch(at) against
-- updatedAt/1000 (epoch-ms -> epoch-seconds).

CREATE TABLE IF NOT EXISTS "case" (
  id         TEXT PRIMARY KEY NOT NULL,
  title      TEXT NOT NULL,
  kind       TEXT NOT NULL DEFAULT 'general',   -- general | purchase
  status     TEXT NOT NULL DEFAULT 'aktiv',     -- aktiv | var-ram | var-masra | kesz
  owner      TEXT,
  due_at     TEXT,
  notes      TEXT,
  archived   INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_case_status ON "case" (status, archived);

CREATE TABLE IF NOT EXISTS case_event (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id        TEXT NOT NULL,
  at             TEXT NOT NULL DEFAULT (datetime('now')),
  actor          TEXT NOT NULL,        -- user | agent
  actor_token_id TEXT,                 -- which agent token, when actor = 'agent'
  kind           TEXT NOT NULL,
  body           TEXT,
  -- RESTRICT, not CASCADE: this table is the audit trail. Cases are
  -- soft-deleted via "case".archived — nothing should ever hard-delete a
  -- case row, so a hard delete must fail loudly instead of silently wiping
  -- the history that exists to record it.
  FOREIGN KEY (case_id) REFERENCES "case"(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_case_event_case ON case_event (case_id, at);

-- Machine writers. Only the hash is stored: reading this table must not yield
-- a usable credential.
CREATE TABLE IF NOT EXISTS agent_token (
  id           TEXT PRIMARY KEY NOT NULL,
  label        TEXT NOT NULL,
  token_hash   TEXT NOT NULL UNIQUE,
  -- Space separated, e.g. 'purchasing:write'. Any scope check MUST split on
  -- whitespace and compare exact tokens — never substring or LIKE matching
  -- (a naive `scopes.includes('purchasing:write')` false-positives on
  -- 'purchasing:writeall').
  scopes       TEXT NOT NULL DEFAULT '',
  active       INTEGER NOT NULL DEFAULT 1,
  -- No default: every caller must choose an expiry so a forgotten token
  -- cannot silently mint a never-expiring credential.
  expires_at   TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT
);
