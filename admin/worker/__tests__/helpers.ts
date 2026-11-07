// Test helpers: better-sqlite3-based D1 emulator + real app instance with
// real migrations. Emulates the D1 prepare/bind/first/all/run surface.
// (notably the ?N -> named-param rewrite below.)
import Database from 'better-sqlite3';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Env } from '../src/types';

const MIGRATIONS = join(dirname(fileURLToPath(import.meta.url)), '..', 'migrations');

class FakeStatement {
  constructor(private db: Database.Database, private sql: string, private params: unknown[] = []) {}
  bind(...params: unknown[]) {
    return new FakeStatement(this.db, this.sql, params);
  }
  private normalized(): { sql: string; params: unknown[] } {
    // D1 uses ?1/?2 positional placeholders; better-sqlite3 does not understand
    // those positionally. Rewrite to named (@p1) so placeholder reuse works.
    if (/\?\d+/.test(this.sql)) {
      const sql = this.sql.replace(/\?(\d+)/g, '@p$1');
      const obj: Record<string, unknown> = {};
      this.params.forEach((v, i) => (obj[`p${i + 1}`] = v));
      return { sql, params: [obj] };
    }
    return { sql: this.sql, params: this.params };
  }
  async first<T = unknown>(column?: string): Promise<T | null> {
    const { sql, params } = this.normalized();
    const row = this.db.prepare(sql).get(...params) as Record<string, unknown> | undefined;
    if (row === undefined) return null;
    if (column !== undefined) {
      if (!Object.prototype.hasOwnProperty.call(row, column)) {
        throw new Error(`D1_ERROR: No such column: ${column}`);
      }
      return (row[column] ?? null) as T;
    }
    return row as T;
  }
  async all<T = unknown>(): Promise<{ results: T[] }> {
    const { sql, params } = this.normalized();
    return { results: this.db.prepare(sql).all(...params) as T[] };
  }
  // D1 exposes raw() (rows as value arrays). Drizzle's D1 driver — and so
  // better-auth through the drizzle adapter — goes through it for every
  // SELECT, so the emulator has to have it or the auth surface cannot be
  // exercised in tests at all.
  async raw<T = unknown[]>(options?: { columnNames?: boolean }): Promise<T[]> {
    const { sql, params } = this.normalized();
    const stmt = this.db.prepare(sql);
    // better-sqlite3 throws on raw(true) for statements that return no data;
    // real D1 just returns []. Match D1, so a future INSERT/UPDATE going
    // through this path reads as an emulator no-op rather than an auth bug.
    if (!stmt.reader) {
      stmt.run(...params);
      return [];
    }
    const rows = stmt.raw(true).all(...params) as unknown[][];
    if (options?.columnNames) return [stmt.columns().map((c) => c.name), ...rows] as T[];
    return rows as T[];
  }
  // Synchronous twin of run(), for use inside a better-sqlite3
  // `db.transaction()` callback — those must be synchronous, so batch() below
  // cannot call the async run().
  runSync(): { success: true; meta: { last_row_id: number; changes: number } } {
    const { sql, params } = this.normalized();
    const info = this.db.prepare(sql).run(...params);
    return { success: true, meta: { last_row_id: Number(info.lastInsertRowid), changes: info.changes } };
  }
  async run(): Promise<{ success: true; meta: { last_row_id: number; changes: number } }> {
    return this.runSync();
  }
}

/** `only` narrows which migration files run — e.g. the product's alone, without the instance band. */
export function makeDb(only: (file: string) => boolean = () => true): { DB: Env['DB']; raw: Database.Database } {
  const raw = new Database(':memory:');
  raw.pragma('foreign_keys = ON');
  for (const f of readdirSync(MIGRATIONS).sort()) {
    if (f.endsWith('.sql') && only(f)) raw.exec(readFileSync(join(MIGRATIONS, f), 'utf8'));
  }
  const DB = {
    prepare: (sql: string) => new FakeStatement(raw, sql),
    // Real D1 wraps batch() in an implicit transaction: all statements commit
    // together, or none do. A loop of individual .run() calls would not
    // reproduce that — a failing statement partway through would leave the
    // earlier ones committed, which is exactly the bug this helper exists to
    // catch. `db.transaction()` gives genuine all-or-nothing semantics.
    batch: async (stmts: FakeStatement[]) => {
      const txn = raw.transaction((list: FakeStatement[]) => list.map((s) => s.runSync()));
      return txn(stmts);
    },
  } as unknown as Env['DB'];
  return { DB, raw };
}

export function makeEnv(overrides: Partial<Env> = {}): Env {
  const { DB } = makeDb();
  return {
    DB,
    ADMIN_EMAILS: 'owner@example.com',
    BETTER_AUTH_URL: 'http://localhost:8787',
    OTP_DRY_RUN: '1',
    ...overrides,
  };
}

export function jsonReq(method: string, body: unknown, headers: Record<string, string> = {}) {
  return {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  };
}
