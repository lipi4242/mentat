// 0202_cases_simplify: description in, waiting_on and category out of the
// base model — without losing a value a row already holds (they move to extra,
// and an extra key of the same name is never overwritten).
import { describe, it, expect } from 'vitest';
import Database from 'better-sqlite3';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'migrations');
const FILE = '0202_cases_simplify.sql';

function before() {
  const db = new Database(':memory:');
  for (const f of readdirSync(DIR).sort()) if (f.endsWith('.sql') && f < FILE) db.exec(readFileSync(join(DIR, f), 'utf8'));
  return db;
}

describe(FILE, () => {
  it('adds description, folds waiting_on/category into extra, drops the columns', () => {
    const db = before();
    const ins = db.prepare(`INSERT INTO cases_case (id, title, waiting_on, category, extra) VALUES (?, ?, ?, ?, ?)`);
    ins.run('01JAB6Z9Q3M8K7T2V5W4X1Y0RA', 'a', 'a biztosító', 'háztartás', '{}');
    ins.run('01JAB6Z9Q3M8K7T2V5W4X1Y0RB', 'b', null, 'adó', '{"category":"saját"}');
    ins.run('01JAB6Z9Q3M8K7T2V5W4X1Y0RC', 'c', null, null, '{"x":1}');
    db.exec(readFileSync(join(DIR, FILE), 'utf8'));
    const cols = (db.prepare(`PRAGMA table_info(cases_case)`).all() as { name: string }[]).map((c) => c.name);
    expect(cols).toContain('description');
    expect(cols).not.toContain('waiting_on');
    expect(cols).not.toContain('category');
    const extra = (id: string) => JSON.parse((db.prepare(`SELECT extra FROM cases_case WHERE id = ?`).get(id) as any).extra);
    expect(extra('01JAB6Z9Q3M8K7T2V5W4X1Y0RA')).toEqual({ waiting_on: 'a biztosító', category: 'háztartás' });
    expect(extra('01JAB6Z9Q3M8K7T2V5W4X1Y0RB')).toEqual({ category: 'saját', category_old: 'adó' });
    expect(extra('01JAB6Z9Q3M8K7T2V5W4X1Y0RC')).toEqual({ x: 1 });
  });
});
