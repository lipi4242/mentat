// Export → restore round trip on the real migrations. The CLI wraps exactly
// these functions around `wrangler d1 execute`; here the same functions run
// against the better-sqlite3 emulator.
import { describe, it, expect } from 'vitest';
import type Database from 'better-sqlite3';
import { makeDb } from './helpers';
import {
  exportDb,
  planRestore,
  assertRestorable,
  restoreSql,
  literal,
  type QueryMany,
} from '../scripts/lib/dump.mjs';

const runner =
  (raw: Database.Database): QueryMany =>
  async (sqls) =>
    sqls.map((s) => raw.prepare(s).all() as Record<string, unknown>[]);

function seeded() {
  const { raw } = makeDb();
  raw.exec(`
    INSERT INTO auth_user (id,name,email,emailVerified,createdAt,updatedAt) VALUES ('u1','Owner','owner@example.com',1,1,1);
    INSERT INTO auth_account (id,accountId,providerId,userId,createdAt,updatedAt) VALUES ('a1','u1','email','u1',1,1);
    INSERT INTO auth_session (id,expiresAt,token,createdAt,updatedAt,userId) VALUES ('s1',9,'live-session',1,1,'u1');
    INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('t1','agent','abc','cases:write','2999-01-01 00:00:00');
    INSERT INTO cases_case (id,title,next_action) VALUES ('01JAB6Z9Q3M8K7T2V5W4X1Y0RS','Gázszámla','it''s "quoted"; DROP TABLE x;');
    INSERT INTO cases_event (case_id,actor,kind) VALUES ('01JAB6Z9Q3M8K7T2V5W4X1Y0RS','user','case.created');
  `);
  return raw;
}

const strip = (d: Record<string, unknown>) => ({ ...d, exported_at: 'x' });

describe('export → restore', () => {
  it('round-trips every data table into a freshly migrated database', async () => {
    const src = seeded();
    const dump = await exportDb(runner(src));

    const { raw: dst } = makeDb();
    const tables = planRestore(dump);
    await assertRestorable(runner(dst), tables);
    dst.exec(restoreSql(dump, tables));

    expect(strip(await exportDb(runner(dst)))).toEqual(strip(dump));
    expect(dst.prepare(`SELECT next_action FROM cases_case`).get()).toEqual({ next_action: 'it\'s "quoted"; DROP TABLE x;' });
  });

  it('keeps the user and the agent tokens, but never live sessions', async () => {
    const dump = await exportDb(runner(seeded()));
    expect(dump.tables.auth_user).toHaveLength(1);
    expect(dump.tables.agent_token).toHaveLength(1);
    expect(dump.tables.auth_session).toBeUndefined();
    expect(dump.skipped).toContain('auth_session');
  });

  it('orders parents before children', async () => {
    const { order } = await exportDb(runner(seeded()));
    expect(order.indexOf('cases_case')).toBeLessThan(order.indexOf('cases_event'));
    expect(order.indexOf('auth_user')).toBeLessThan(order.indexOf('auth_account'));
  });

  it('exports only the named tables, and refuses an unknown one', async () => {
    const src = seeded();
    const dump = await exportDb(runner(src), { only: ['cases_case', 'cases_event'] });
    expect(Object.keys(dump.tables).sort()).toEqual(['cases_case', 'cases_event']);
    await expect(exportDb(runner(src), { only: ['nope'] })).rejects.toThrow(/nope/);
  });

  it('refuses to restore over existing rows', async () => {
    const dump = await exportDb(runner(seeded()));
    await expect(assertRestorable(runner(seeded()), planRestore(dump))).rejects.toThrow(/not empty/);
  });

  it('refuses a table the target does not have, unless narrowed away', async () => {
    const dump = await exportDb(runner(seeded()));
    const { raw: dst } = makeDb();
    dst.exec('DROP TABLE cases_event');
    await expect(assertRestorable(runner(dst), planRestore(dump))).rejects.toThrow(/cases_event/);
    await expect(assertRestorable(runner(dst), planRestore(dump, { only: ['cases_case'] }))).resolves.toBeUndefined();
  });

  it('rejects a file that is not an export of this format and version', () => {
    expect(() => planRestore({ format: 'other' })).toThrow(/not a/);
    expect(() => planRestore({ format: 'mentat-admin-export', version: 2 })).toThrow(/version/);
  });

  it('writes values only as escaped literals, never guessing at non-scalars', () => {
    expect(literal("a'b")).toBe("'a''b'");
    expect(literal(null)).toBe('NULL');
    expect(literal(true)).toBe('1');
    expect(literal(2.5)).toBe('2.5');
    expect(() => literal({ a: 1 })).toThrow(/non-scalar/);
    expect(() => literal(Number.NaN)).toThrow(/non-finite/);
  });
});
