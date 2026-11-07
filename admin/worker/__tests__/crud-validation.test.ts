import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { jsonReq } from './helpers';
import { fixture } from './fixture-crud';
import { registerCrud } from '../src/core/crud';
import type { AppEnv } from '../src/types';

// The generic core, on the synthetic widget plugin (fixture-crud.ts) — the
// core no longer ships a table of its own to test it on.
async function setup() {
  const f = await fixture();
  const maker = (await (await f.app.request('/api/makers', jsonReq('POST', { name: 'Acme' }, f.h), f.env)).json()) as { id: string };
  return { ...f, makerId: maker.id };
}

const idOf = async (res: Response) => {
  expect(res.status).toBe(200);
  return ((await res.json()) as { id: string }).id;
};

/**
 * M1 — the edit form deliberately sends `null` for a blanked field (omitting
 * it would read as "unchanged"), and PATCH skips the `required` check because
 * a PATCH is legitimately partial. A NOT NULL column blanked on an edit form
 * therefore reached SQLite as a constraint violation and came back as a 500
 * advising the user to retry, which could never work.
 */
describe('explicit null on a NOT NULL column', () => {
  it('400s a PATCH clearing widget.sku, naming the field', async () => {
    const { app, env, h, makerId } = await setup();
    const id = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A' }, h), env));
    const res = await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { sku: null }, h), env);
    expect(res.status).toBe(400);
    expect(((await res.json()) as any).error).toMatch(/sku/);
  });


  it('400s the same on POST rather than letting it reach SQLite', async () => {
    const { app, env, h, makerId } = await setup();
    const res = await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: null }, h), env);
    expect(res.status).toBe(400);
  });

  it('still lets a nullable column be cleared', async () => {
    const { app, env, raw, h, makerId } = await setup();
    const id = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A', qty: 2 }, h), env));
    const res = await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { qty: null }, h), env);
    expect(res.status).toBe(200);
    expect((raw.prepare(`SELECT qty FROM widget WHERE id = ?`).get(id) as any).qty).toBeNull();
  });

  it('rejects a spec whose notNull names a column it cannot write', () => {
    expect(() =>
      registerCrud(new Hono<AppEnv>(), {
        path: 'x',
        table: 'x',
        scope: 'x:write',
        columns: ['title'],
        notNull: ['title', 'kind'],
      }),
    ).toThrow(/kind/);
  });
});
