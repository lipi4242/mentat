// 0501 (Codex-review): a csupasz hatókört a SAJÁT flottáján belül írja át (box-név → box:, más →
// agent:), és a kétértelmű nevet (ugyanabban a flottában box és ágens is) nem írja át csendben:
// a migráció megáll.
import Database from 'better-sqlite3';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'migrations');
const before = (db: Database.Database) => {
  for (const f of readdirSync(DIR).sort()) if (f.endsWith('.sql') && f < '0501') db.exec(readFileSync(join(DIR, f), 'utf8'));
  db.exec(`INSERT INTO flotta_fleet (id, name, updated_at) VALUES ('f1','F','x'), ('f2','G','x');
    INSERT INTO flotta_box (id, fleet_id, name, created_at) VALUES ('b1','f1','alfa','x'), ('b2','f2','beta','x');`);
};
const m0501 = readFileSync(join(DIR, '0501_flotta_menedzser.sql'), 'utf8');
const mgr = (db: Database.Database, id: string, fleet: string, scope: string) =>
  db.prepare(`INSERT INTO flotta_manager (id, fleet_id, principal_id, agent, scope, rank, created_at) VALUES (?, ?, 'p', 'a', ?, 1, 'x')`).run(id, fleet, scope);

describe('0501 scope rewrite', () => {
  it('correlates by fleet: a box name of ANOTHER fleet stays an agent scope', () => {
    const db = new Database(':memory:');
    before(db);
    mgr(db, 'm1', 'f1', 'alfa'); mgr(db, 'm2', 'f1', 'beta'); mgr(db, 'm3', 'f1', '*');
    db.exec(m0501);
    expect(db.prepare('SELECT id, scope FROM flotta_manager ORDER BY id').all()).toEqual([
      { id: 'm1', scope: 'box:alfa' }, { id: 'm2', scope: 'agent:beta' }, { id: 'm3', scope: '*' }]);
    expect(db.prepare(`SELECT name FROM sqlite_master WHERE name = 'flotta_0501_guard'`).all()).toEqual([]);
  });

  it('an ambiguous bare name (both a box and an agent in the same fleet) stops the migration', () => {
    const db = new Database(':memory:');
    before(db);
    db.exec(`INSERT INTO flotta_agent (id, fleet_id, name, box_id, last_seen_at, result_json) VALUES ('a1','f1','alfa','b1','x','{}')`);
    mgr(db, 'm1', 'f1', 'alfa');
    expect(() => db.exec(m0501)).toThrow(/CHECK constraint failed/);
  });
});
