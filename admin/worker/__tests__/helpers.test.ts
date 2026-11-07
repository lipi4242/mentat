import { describe, it, expect } from 'vitest';
import { makeDb } from './helpers';

describe('D1 emulator (helpers.makeDb)', () => {
  it('inserts with ?1/?2 placeholders and reads the row back with .first()', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE scratch (id INTEGER PRIMARY KEY, a TEXT, b TEXT)');

    await DB.prepare('INSERT INTO scratch (a, b) VALUES (?1, ?2)').bind('foo', 'bar').run();
    const row = await DB.prepare('SELECT * FROM scratch WHERE a = ?1').bind('foo').first<{ a: string; b: string }>();

    expect(row).toEqual({ id: 1, a: 'foo', b: 'bar' });
  });

  it('rewrites a repeated placeholder number correctly (?1 used twice)', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE scratch (id INTEGER PRIMARY KEY, a TEXT, b TEXT)');
    raw.exec("INSERT INTO scratch (a, b) VALUES ('x', 'y'), ('y', 'z'), ('q', 'q')");

    const { results } = await DB.prepare('SELECT * FROM scratch WHERE a = ?1 OR b = ?1')
      .bind('y')
      .all<{ id: number; a: string; b: string }>();

    // Row 1 matches via b='y'; row 2 matches via a='y'. Row 3 matches neither.
    expect(results.map((r) => r.id).sort()).toEqual([1, 2]);
  });

  it('.all() returns { results: [...] }, not a bare array', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE scratch (id INTEGER PRIMARY KEY, a TEXT)');
    raw.exec("INSERT INTO scratch (a) VALUES ('x'), ('y')");

    const res = await DB.prepare('SELECT * FROM scratch').all();

    expect(Array.isArray(res)).toBe(false);
    expect(res).toHaveProperty('results');
    expect(Array.isArray(res.results)).toBe(true);
    expect(res.results).toHaveLength(2);
  });

  it('.run() reports success, changes and last_row_id', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE scratch (id INTEGER PRIMARY KEY, a TEXT)');

    const res = await DB.prepare('INSERT INTO scratch (a) VALUES (?1)').bind('one').run();
    expect(res.success).toBe(true);
    expect(res.meta.changes).toBe(1);
    expect(res.meta.last_row_id).toBe(1);

    const res2 = await DB.prepare('INSERT INTO scratch (a) VALUES (?1)').bind('two').run();
    expect(res2.meta.last_row_id).toBe(2);
  });

  it('.first(column) returns the scalar column value, not the row', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE scratch (id INTEGER PRIMARY KEY, a TEXT, b TEXT)');
    raw.exec("INSERT INTO scratch (a, b) VALUES ('foo', 'bar')");

    const value = await DB.prepare('SELECT * FROM scratch WHERE id = ?1').bind(1).first<string>('a');
    expect(value).toBe('foo');

    await expect(
      DB.prepare('SELECT * FROM scratch WHERE id = ?1').bind(1).first('nope'),
    ).rejects.toThrow(/D1_ERROR/);

    const noRow = await DB.prepare('SELECT * FROM scratch WHERE id = ?1').bind(999).first('a');
    expect(noRow).toBeNull();

    const wholeRow = await DB.prepare('SELECT * FROM scratch WHERE id = ?1').bind(1).first();
    expect(wholeRow).toEqual({ id: 1, a: 'foo', b: 'bar' });
  });

  it('enforces foreign keys', async () => {
    const { DB, raw } = makeDb();
    raw.exec('CREATE TABLE parent (id INTEGER PRIMARY KEY)');
    raw.exec(
      'CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))',
    );

    await expect(
      DB.prepare('INSERT INTO child (parent_id) VALUES (?1)').bind(999).run(),
    ).rejects.toThrow();
  });
});
