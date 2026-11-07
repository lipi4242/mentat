// 0101 drops the retired purchasing tables. Applied step by step, as on the
// live database: everything up to 0100 with real rows in it, then 0101. The
// user, the agent tokens and the core cases must come through untouched.
import { describe, it, expect } from 'vitest';
import Database from 'better-sqlite3';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { RETIRED_BANDS } from '../../config/plugins';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'migrations');
const sql = (f: string) => readFileSync(join(DIR, f), 'utf8');
const RETIRE = '0101_purchasing_retire.sql';

const tables = (db: Database.Database) =>
  (db.prepare(`SELECT name FROM sqlite_master WHERE type = 'table'`).all() as { name: string }[]).map((r) => r.name);

describe(RETIRE, () => {
  it('drops every purchasing table and keeps the user, the tokens and the cases', () => {
    const db = new Database(':memory:');
    db.pragma('foreign_keys = ON');
    for (const f of readdirSync(DIR).filter((f) => f.endsWith('.sql') && f < RETIRE).sort()) db.exec(sql(f));
    db.exec(`
      INSERT INTO auth_user (id,name,email,emailVerified,createdAt,updatedAt) VALUES ('u1','Owner','owner@example.com',1,1,1);
      INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('t1','agent','h','cases:write','2999-01-01 00:00:00');
      INSERT INTO "case" (id,title,kind) VALUES ('c1','Teszt','purchase');
      INSERT INTO case_event (case_id,actor,kind) VALUES ('c1','user','case.created');
      INSERT INTO purchase_need (id,case_id) VALUES ('n1','c1');
      INSERT INTO need_item (id,need_id,description) VALUES ('ni1','n1','x');
      INSERT INTO supplier (id,name) VALUES ('s1','Bolt');
      INSERT INTO product (id,name) VALUES ('p1','Termék');
      INSERT INTO offer (id,supplier_id,product_id) VALUES ('o1','s1','p1');
      INSERT INTO purchase_intent (id,title,supplier_id) VALUES ('i1','Rendelés','s1');
      INSERT INTO intent_item (id,intent_id,offer_id) VALUES ('ii1','i1','o1');
      INSERT INTO allocation (id,intent_item_id,need_item_id) VALUES ('a1','ii1','ni1');
    `);

    db.exec(sql(RETIRE));

    const left = tables(db);
    const purchasing = RETIRED_BANDS.find((b) => b.id === 'purchasing')!.tables;
    expect(left.filter((t) => purchasing.includes(t))).toEqual([]);
    expect(db.prepare(`SELECT email FROM auth_user`).all()).toEqual([{ email: 'owner@example.com' }]);
    expect(db.prepare(`SELECT id FROM agent_token`).all()).toEqual([{ id: 't1' }]);
    expect(db.prepare(`SELECT count(*) n FROM case_event`).get()).toEqual({ n: 1 });
    expect(db.pragma('foreign_key_check')).toEqual([]);
  });
});
