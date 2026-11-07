import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { registerCrud } from '../src/core/crud';
import { hashToken } from '../src/lib/tokens';
import type { AppEnv } from '../src/types';

/**
 * A spec whose eventStmt always fails (targets a table that does not exist).
 * Used to prove that `registerCrud` commits the row and its event atomically
 * via `DB.batch()` — if the event half fails, the row half must not persist.
 */
function appWithFaultyEvent() {
  const app = new Hono<AppEnv>();
  registerCrud(app, {
    path: 'notes',
    table: 'note',
    columns: ['title'],
    scope: 'cases:write',
    touchUpdatedAt: false,
    eventStmt: (c, id) => c.env.DB.prepare(`INSERT INTO no_such_table (x) VALUES (?1)`).bind(id),
  });
  return app;
}

describe('registerCrud atomicity', () => {
  it('leaves no row behind when the paired event statement fails', async () => {
    const { DB, raw } = makeDb();
    raw.exec(`CREATE TABLE note (id TEXT PRIMARY KEY NOT NULL, title TEXT)`);
    raw
      .prepare(
        `INSERT INTO agent_token (id, label, token_hash, scopes, expires_at) VALUES ('tok1','agent',?,'cases:write','2999-01-01T00:00:00Z')`,
      )
      .run(await hashToken('plain'));
    const env = makeEnv({ DB });
    const app = appWithFaultyEvent();

    const res = await app.request(
      '/api/notes',
      jsonReq('POST', { title: 'orphan?' }, { 'X-Mentat-Token': 'plain' }),
      env,
    );
    expect(res.status).toBe(500);

    const row = raw.prepare(`SELECT COUNT(*) AS n FROM note`).get() as any;
    expect(row.n).toBe(0);
  });
});
