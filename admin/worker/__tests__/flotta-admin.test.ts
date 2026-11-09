// 11-07: box-regisztráció (a token úgy készül, mint a többi gépi token, de csak
// flotta:report), a flotta beállítása (felelős ágens, tulajdonos, küszöbök), az
// olvasó végpontok, és a cron bekötése a Worker exportjába.
import { afterEach, describe, expect, it, vi } from 'vitest';
import worker, { runScheduled } from '../src/index';
import { flottaPlugin } from '../src/plugins/flotta';
import { jsonReq } from './helpers';
import { signIn } from './sign-in';
import { flottaApp, green, min, red } from './flotta-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

async function admin() {
  const f = await flottaApp();
  f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  f.env.BETTER_AUTH_URL = 'http://localhost:8787';
  f.env.OTP_DRY_RUN = '1';
  const cookie = (await signIn(f.app, f.env, 'owner@example.com'))!;
  const call = async (method: string, path: string, body?: unknown, headers: Record<string, string> = { cookie }) => {
    const res = await f.app.request(path, body === undefined ? { method, headers } : jsonReq(method, body, headers), f.env);
    return { status: res.status, body: await res.json() as any };
  };
  return { ...f, call, cookie };
}

describe('flotta admin API', () => {
  it('registers a box with a freshly minted flotta:report-only token, shown once, hash stored', async () => {
    const f = await admin();
    const res = await f.call('POST', '/api/flotta/v1/boxes', { name: 'gamma' });
    expect(res.status).toBe(201);
    expect(res.body.token).toMatch(/^mentat_/);
    const row = f.raw.prepare('SELECT label, scopes, token_hash FROM agent_token WHERE id = ?').get(res.body.token_id) as any;
    expect(row).toMatchObject({ label: 'box-gamma', scopes: 'flotta:report' });
    expect(row.token_hash).not.toContain(res.body.token);
    const rep = await f.app.request('/api/flotta/v1/report', jsonReq('POST', { box: 'gamma', agents: [green('kertesz')] },
      { 'X-Mentat-Token': res.body.token }), f.env);
    expect(rep.status).toBe(200);
    expect((await f.call('POST', '/api/flotta/v1/boxes', { name: 'gamma' })).status).toBe(409);
  });

  it('binds an existing token only if its scope is exactly flotta:report', async () => {
    const f = await admin();
    expect((await f.call('POST', '/api/flotta/v1/boxes', { name: 'x1', token_id: 'gondnok-agent' })).status).toBe(422);
    f.raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('wide','wide','h1','flotta:report todo:write','2999-01-01T00:00:00Z')`).run();
    expect((await f.call('POST', '/api/flotta/v1/boxes', { name: 'x2', token_id: 'wide' })).status).toBe(422);
    f.raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('narrow','narrow','h2','flotta:report','2999-01-01T00:00:00Z')`).run();
    const ok = await f.call('POST', '/api/flotta/v1/boxes', { name: 'x3', token_id: 'narrow' });
    expect(ok.status).toBe(201);
    expect(ok.body.token).toBeUndefined();
  });

  it('rotates a box token: the old one stops working at once', async () => {
    const f = await admin();
    const res = await f.call('POST', '/api/flotta/v1/boxes/beta/token', {});
    expect(res.status).toBe(200);
    expect((await f.report('beta', [green('szervezo')])).status).toBe(401);
    const rep = await f.app.request('/api/flotta/v1/report', jsonReq('POST', { box: 'beta', agents: [] }, { 'X-Mentat-Token': res.body.token }), f.env);
    expect(rep.status).toBe(200);
  });

  it('configures owner e-mail and thresholds; the manager list is NOT writable here (publisher only)', async () => {
    const f = await admin();
    const set = await f.call('PUT', '/api/flotta/v1/fleets/default', { owner_email: 'Boss@Example.com', escalate_min: 45 });
    expect(set.status).toBe(200);
    expect(set.body).toMatchObject({ owner_email: 'boss@example.com', escalate_min: 45 });
    expect((await f.call('PUT', '/api/flotta/v1/fleets/default', { managers: [{ handle: 'gondnok' }] })).status).toBe(409);
    expect((await f.call('PUT', '/api/flotta/v1/fleets/default', { deadman_min: 0 })).status).toBe(400);
    // gépi token (akár egy menedzseré) nem állíthat
    expect((await f.call('PUT', '/api/flotta/v1/fleets/default', { escalate_min: 1 }, { 'X-Mentat-Token': 'plain-gondnok-agent' })).status).toBe(401);
  });

  it('status lists boxes with report age, agents with their checks, and incidents with history', async () => {
    const f = await admin();
    await f.report('beta', [red('vilma', 'kuldes')]);
    const s = await f.call('GET', '/api/flotta/v1/status');
    expect(s.status).toBe(200);
    const beta = s.body.boxes.find((b: any) => b.name === 'beta');
    expect(beta).toMatchObject({ fleet_version: '1.4.0' });
    expect(typeof beta.age_min).toBe('number');
    expect(s.body.boxes.find((b: any) => b.name === 'gondnok')).toMatchObject({ age_min: null, stale: true });
    expect(s.body.agents[0]).toMatchObject({ name: 'vilma', box_name: 'beta', result: { red: [{ check: 'kuldes' }] } });
    expect(s.body.fleets[0].effective_owner_email).toBe('owner@example.com');
    const inc = await f.call('GET', `/api/flotta/v1/incidents/${s.body.incidents[0].id}`);
    expect(inc.body.events.map((e: any) => e.kind)).toEqual(['opened', 'uncovered']);   // a beta boxot senki nem éri el
    expect(inc.body.claim_hash).toBeUndefined();
    expect(s.body.fleets[0].coverage.uncovered.map((u: any) => u.target)).toEqual(['agent:vilma', 'box:beta', 'box:gondnok']);
    // flotta:read token olvashat, todo:write nem
    f.raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('r','r',?,'flotta:read','2999-01-01T00:00:00Z')`)
      .run(await (await import('../src/lib/tokens')).hashToken('plain-r'));
    expect((await f.call('GET', '/api/flotta/v1/status', undefined, { 'X-Mentat-Token': 'plain-r' })).status).toBe(200);
    expect((await f.call('GET', '/api/flotta/v1/status', undefined, { 'X-Mentat-Token': 'plain-gondnok-agent' })).status).toBe(403);
  });

  it('disabling a box resolves its dead-man incident and stops new ones', async () => {
    const f = await admin();
    await f.cron(min(31));
    expect(f.incidents().filter(i => i.status === 'open')).toHaveLength(2);
    expect((await f.call('POST', '/api/flotta/v1/boxes/beta/disable', {})).status).toBe(200);
    await f.cron(min(40));
    expect(f.incidents().filter(i => i.status === 'open').map(i => i.subject)).toEqual(['box:gondnok']);
  });
});

describe('flotta cron wiring', () => {
  it('the Worker export has a scheduled handler that runs the plugin cron', async () => {
    const f = await flottaApp();
    expect(typeof (worker as any).scheduled).toBe('function');
    const waits: Promise<unknown>[] = [];
    (worker as any).scheduled({}, f.env, { waitUntil: (p: Promise<unknown>) => waits.push(p) });
    await Promise.all(waits);
    await runScheduled(f.env, [flottaPlugin], min(31));
    expect(f.incidents().map(i => i.check_key)).toEqual(['deadman', 'deadman']);
  });
});
