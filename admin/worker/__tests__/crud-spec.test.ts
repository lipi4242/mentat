import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { registerCrud } from '../src/core/crud';
import type { AppEnv } from '../src/types';

/**
 * These assertions run at registration time — i.e. at module import, which is
 * what every other test file here triggers by importing `src/index`. A broken
 * spec is a startup error, never a request-time surprise.
 */
describe('assertValidSpec: where-columns must be writable', () => {
  const base = { path: 'x', table: 'x', scope: 'x:write' };

  it('rejects a spec that filters on a column it does not allow writing', () => {
    // Exactly the H1 shape: `archived = 0` hides archived rows, but `archived`
    // is not writable, so nothing can ever archive one.
    expect(() =>
      registerCrud(new Hono<AppEnv>(), { ...base, columns: ['title'], where: 'archived = 0' }),
    ).toThrow(/archived/);
  });

  it('accepts a filter on a column that is writable', () => {
    expect(() =>
      registerCrud(new Hono<AppEnv>(), { ...base, columns: ['title', 'archived'], where: 'archived = 0' }),
    ).not.toThrow();
  });

  it('ignores SQL keywords and literals when reading the filter', () => {
    expect(() =>
      registerCrud(new Hono<AppEnv>(), {
        ...base,
        columns: ['archived', 'status'],
        where: "archived = 0 AND status IS NOT NULL AND status <> 'kesz'",
      }),
    ).not.toThrow();
  });
});
