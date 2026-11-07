// Agent tokens from the admin UI: minted, listed and revoked by a signed-in
// admin only. The plaintext is in the mint response and nowhere else.
import { describe, it, expect } from 'vitest';
import app from '../src/index';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { signIn } from './sign-in';

const ADMIN = 'owner@example.com';

async function admin() {
  const { DB, raw } = makeDb();
  const env = makeEnv({ DB, BETTER_AUTH_SECRET: 'test-secret-not-a-real-one' });
  const cookie = (await signIn(app, env, ADMIN))!;
  expect(cookie).toBeTruthy();
  return { env, raw, h: { cookie } };
}

const mint = (env: any, h: any, body: unknown) => app.request('/api/tokens', jsonReq('POST', body, h), env);

describe('agent tokens (admin UI)', () => {
  it('mints a token that works once, shows it once, and stores only its hash', async () => {
    const { env, raw, h } = await admin();
    const res = await mint(env, h, { label: 'agent1', scopes: 'cases:write', days: 90 });
    expect(res.status).toBe(200);
    const { id, token, expires_at } = (await res.json()) as any;
    expect(token).toMatch(/^mentat_[A-Za-z0-9_-]{43}$/);
    expect(expires_at).toMatch(/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/);

    const stored = raw.prepare(`SELECT * FROM agent_token WHERE id = ?`).get(id) as any;
    expect(JSON.stringify(stored)).not.toContain(token);

    const list = (await (await app.request('/api/tokens', { headers: h }, env)).json()) as any[];
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ id, label: 'agent1', scopes: 'cases:write', active: 1 });
    expect(list[0]).not.toHaveProperty('token_hash');

    const used = await app.request('/api/cases/01JAB6Z9Q3M8K7T2V5W4X1Y0RS', jsonReq('PUT', { title: 'x' }, { 'X-Mentat-Token': token }), env);
    expect(used.status).toBe(201);
  });

  it('revokes: the token stops working and stays listed as inactive', async () => {
    const { env, h } = await admin();
    const { id, token } = (await (await mint(env, h, { label: 'a', scopes: ['cases:write'], days: 1 })).json()) as any;
    expect((await app.request(`/api/tokens/${id}/revoke`, { method: 'POST', headers: h }, env)).status).toBe(200);
    const used = await app.request('/api/cases', { headers: { 'X-Mentat-Token': token } }, env);
    expect(used.status).toBe(401);
    const list = (await (await app.request('/api/tokens', { headers: h }, env)).json()) as any[];
    expect(list[0]).toMatchObject({ id, active: 0 });
    expect((await app.request(`/api/tokens/nope/revoke`, { method: 'POST', headers: h }, env)).status).toBe(404);
  });

  it.each([
    [{ label: '', scopes: 'cases:write', days: 9 }, /label/],
    [{ label: 'a', scopes: 'cases', days: 9 }, /scope/],
    [{ label: 'a', scopes: '', days: 9 }, /scope/],
    [{ label: 'a', scopes: 'cases:write', days: 0 }, /days/],
    [{ label: 'a', scopes: 'cases:write', days: 366 }, /days/],
  ])('400s an invalid mint request %#', async (body, msg) => {
    const { env, h } = await admin();
    const res = await mint(env, h, body);
    expect(res.status).toBe(400);
    expect(((await res.json()) as any).error).toMatch(msg);
  });

  it('refuses everyone but a signed-in admin — an agent token cannot mint tokens', async () => {
    const { env, h } = await admin();
    const { token } = (await (await mint(env, h, { label: 'a', scopes: 'cases:write tokens:write', days: 9 })).json()) as any;
    const agent = { 'X-Mentat-Token': token };
    expect((await mint(env, agent, { label: 'b', scopes: 'cases:write', days: 9 })).status).toBe(401);
    expect((await app.request('/api/tokens', { headers: agent }, env)).status).toBe(401);
    expect((await mint(env, {}, { label: 'b', scopes: 'cases:write', days: 9 })).status).toBe(401);
  });
});
