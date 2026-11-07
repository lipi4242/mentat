-- Mentat Admin migration 0001 — better-auth tables (camelCase columns).
-- The camelCase names match better-auth's own field names — the Drizzle
-- adapter and any hand-written SQL must see the same names.

CREATE TABLE IF NOT EXISTS auth_user (
  id            TEXT PRIMARY KEY NOT NULL,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL,
  emailVerified INTEGER NOT NULL,
  image         TEXT,
  createdAt     INTEGER NOT NULL,
  updatedAt     INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique ON auth_user (email);

CREATE TABLE IF NOT EXISTS auth_session (
  id        TEXT PRIMARY KEY NOT NULL,
  expiresAt INTEGER NOT NULL,
  token     TEXT NOT NULL,
  createdAt INTEGER NOT NULL,
  updatedAt INTEGER NOT NULL,
  ipAddress TEXT,
  userAgent TEXT,
  userId    TEXT NOT NULL,
  FOREIGN KEY (userId) REFERENCES auth_user(id) ON UPDATE no action ON DELETE cascade
);
CREATE UNIQUE INDEX IF NOT EXISTS auth_session_token_unique ON auth_session (token);
CREATE INDEX IF NOT EXISTS idx_auth_session_user ON auth_session (userId);

CREATE TABLE IF NOT EXISTS auth_account (
  id                    TEXT PRIMARY KEY NOT NULL,
  accountId             TEXT NOT NULL,
  providerId            TEXT NOT NULL,
  userId                TEXT NOT NULL,
  accessToken           TEXT,
  refreshToken          TEXT,
  idToken               TEXT,
  accessTokenExpiresAt  INTEGER,
  refreshTokenExpiresAt INTEGER,
  scope                 TEXT,
  password              TEXT,
  createdAt             INTEGER NOT NULL,
  updatedAt             INTEGER NOT NULL,
  FOREIGN KEY (userId) REFERENCES auth_user(id) ON UPDATE no action ON DELETE cascade
);
CREATE INDEX IF NOT EXISTS idx_auth_account_user ON auth_account (userId);

CREATE TABLE IF NOT EXISTS auth_verification (
  id         TEXT PRIMARY KEY NOT NULL,
  identifier TEXT NOT NULL,
  value      TEXT NOT NULL,
  expiresAt  INTEGER NOT NULL,
  createdAt  INTEGER NOT NULL,
  updatedAt  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_verification_identifier ON auth_verification (identifier);

CREATE TABLE IF NOT EXISTS auth_rate_limit (
  id          TEXT PRIMARY KEY NOT NULL,
  key         TEXT,
  count       INTEGER,
  lastRequest INTEGER
);
