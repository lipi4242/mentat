// A synthetic plugin for testing the generic CRUD core without any real
// plugin. The purchasing plugin used to be the only thing exercising upserts,
// CHECK / FOREIGN KEY mapping and boolean coercion; with it gone, these
// behaviours of the core must not lose their tests.
import { Hono } from 'hono';
import { makeDb, makeEnv } from './helpers';
import { hashToken } from '../src/lib/tokens';
import { registerCrud } from '../src/core/crud';
import type { AppEnv } from '../src/types';

const FIXTURE_SQL = `
CREATE TABLE widget_maker (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL);
CREATE TABLE widget (
  id        TEXT PRIMARY KEY NOT NULL,
  maker_id  TEXT NOT NULL,
  sku       TEXT NOT NULL,
  qty       REAL,
  in_stock  INTEGER,
  status    TEXT NOT NULL DEFAULT 'draft',
  CHECK (qty IS NULL OR qty >= 0),
  CHECK (status IN ('draft', 'live')),
  FOREIGN KEY (maker_id) REFERENCES widget_maker(id)
);
CREATE UNIQUE INDEX widget_maker_sku ON widget (maker_id, sku);
`;

const SCOPE = 'widgets:write';

export async function fixture(scopes = SCOPE) {
  const { DB, raw } = makeDb();
  raw.exec(FIXTURE_SQL);
  raw
    .prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('tok1','agent',?,?,'2999-01-01T00:00:00Z')`)
    .run(await hashToken('plain'), scopes);
  const app = new Hono<AppEnv>();
  registerCrud(app, { path: 'makers', table: 'widget_maker', columns: ['name'], scope: SCOPE, required: ['name'], notNull: ['name'], touchUpdatedAt: false });
  registerCrud(app, {
    path: 'widgets',
    table: 'widget',
    columns: ['maker_id', 'sku', 'qty', 'in_stock', 'status'],
    scope: SCOPE,
    required: ['maker_id', 'sku'],
    notNull: ['maker_id', 'sku', 'status'],
    touchUpdatedAt: false,
    conflictColumns: ['maker_id', 'sku'],
  });
  return { app, raw, env: makeEnv({ DB }), h: { 'X-Mentat-Token': 'plain' } };
}
