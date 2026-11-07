// Generic CRUD behaviour, on the synthetic fixture plugin (fixture-crud.ts).
import { describe, it, expect } from 'vitest';
import { jsonReq } from './helpers';
import { fixture } from './fixture-crud';

const idOf = async (res: Response) => {
  expect(res.status).toBe(200);
  return ((await res.json()) as { id: string }).id;
};

async function withMaker() {
  const f = await fixture();
  const makerId = await idOf(await f.app.request('/api/makers', jsonReq('POST', { name: 'Acme' }, f.h), f.env));
  return { ...f, makerId };
}

describe('generic CRUD', () => {
  it('rejects a token without the scope', async () => {
    const { app, env, h } = await fixture('cases:write');
    expect((await app.request('/api/makers', jsonReq('POST', { name: 'x' }, h), env)).status).toBe(403);
  });

  it('re-posting the same conflict key updates the row in place', async () => {
    const { app, env, raw, h, makerId } = await withMaker();
    const first = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A', qty: 1 }, h), env));
    const second = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A', qty: 7 }, h), env));
    expect(second).toBe(first);
    expect(raw.prepare(`SELECT count(*) n, max(qty) q FROM widget`).get()).toEqual({ n: 1, q: 7 });
  });

  it('maps a foreign-key violation to 409', async () => {
    const { app, env, h } = await fixture();
    expect((await app.request('/api/widgets', jsonReq('POST', { maker_id: 'nope', sku: 'A' }, h), env)).status).toBe(409);
  });

  it('coerces a JSON boolean to 0/1', async () => {
    const { app, env, raw, h, makerId } = await withMaker();
    const id = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A', in_stock: true }, h), env));
    expect((raw.prepare(`SELECT in_stock FROM widget WHERE id = ?`).get(id) as any).in_stock).toBe(1);
    expect((await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { in_stock: false }, h), env)).status).toBe(200);
    expect((raw.prepare(`SELECT in_stock FROM widget WHERE id = ?`).get(id) as any).in_stock).toBe(0);
  });

  it('400s a POST missing a required field, naming it', async () => {
    const { app, env, h } = await fixture();
    const res = await app.request('/api/widgets', jsonReq('POST', { sku: 'A' }, h), env);
    expect(res.status).toBe(400);
    expect(((await res.json()) as any).error).toMatch(/maker_id/);
  });

  it('400s a non-scalar value on POST and on PATCH', async () => {
    const { app, env, h, makerId } = await withMaker();
    expect((await app.request('/api/makers', jsonReq('POST', { name: { nested: true } }, h), env)).status).toBe(400);
    expect((await app.request(`/api/makers/${makerId}`, jsonReq('PATCH', { name: ['x'] }, h), env)).status).toBe(400);
  });

  it('does not require all fields on a PATCH, but 400s clearing a NOT NULL one', async () => {
    const { app, env, h, makerId } = await withMaker();
    const id = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A' }, h), env));
    expect((await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { qty: 2 }, h), env)).status).toBe(200);
    const res = await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { maker_id: null }, h), env);
    expect(res.status).toBe(400);
    expect(((await res.json()) as any).error).toMatch(/maker_id/);
  });

  it('maps CHECK violations to 400 on POST and on PATCH', async () => {
    const { app, env, h, makerId } = await withMaker();
    expect((await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'A', status: 'bogus' }, h), env)).status).toBe(400);
    const id = await idOf(await app.request('/api/widgets', jsonReq('POST', { maker_id: makerId, sku: 'B' }, h), env));
    expect((await app.request(`/api/widgets/${id}`, jsonReq('PATCH', { qty: -2 }, h), env)).status).toBe(400);
  });
});
