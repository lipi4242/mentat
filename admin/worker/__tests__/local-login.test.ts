// The local sign-in link: `npm run login-link` writes a one-time row, the
// worker trades it for a session — only on a local admin, only on loopback.
import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { PLUGINS } from '../../config/plugins';
import { makeDb, makeEnv } from './helpers';
import { newLink } from '../scripts/lib/login-link.mjs';

const ORIGIN = 'http://localhost:8787';
const SECRET = 'test-secret-0123456789abcdef0123456789abcdef';

function setup(overrides = {}) {
  const { DB, raw } = makeDb();
  const env = makeEnv({ DB, BETTER_AUTH_SECRET: SECRET, ...overrides });
  return { app: createApp(PLUGINS), env, raw };
}

function seed(raw: any, opts: { email?: string; now?: number } = {}) {
  const link = newLink({ origin: ORIGIN, email: opts.email ?? 'owner@example.com', now: opts.now });
  for (const sql of link.sql) raw.exec(sql);
  return link;
}

const path = (url: string) => new URL(url).pathname;

describe('GET /api/local-login/:token', () => {
  it('signs the owner in once and lands on the UI', async () => {
    const { app, env, raw } = setup();
    const link = seed(raw);
    const res = await app.request(link.url, {}, env);
    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe('/');
    const cookie = res.headers.get('set-cookie')!.split(';')[0];
    expect(cookie).toMatch(/session_token=/);
    const tokens = await app.request(`${ORIGIN}/api/tokens`, { headers: { cookie } }, env);
    expect(tokens.status).toBe(200);

    const again = await app.request(link.url, {}, env);
    expect(again.status).toBe(410);
  });

  it('refuses an expired link', async () => {
    const { app, env, raw } = setup();
    const link = seed(raw, { now: Date.now() - 11 * 60 * 1000 });
    expect((await app.request(link.url, {}, env)).status).toBe(410);
  });

  it('refuses an unknown token without a hint', async () => {
    const { app, env } = setup();
    expect((await app.request(`${ORIGIN}/api/local-login/nope`, {}, env)).status).toBe(410);
  });

  it('refuses an address that may not sign in', async () => {
    const { app, env, raw } = setup();
    const link = seed(raw, { email: 'someone@example.com' });
    expect((await app.request(link.url, {}, env)).status).toBe(403);
  });

  it('does not exist on a deployed admin', async () => {
    const { app, env, raw } = setup({ BETTER_AUTH_URL: 'https://admin.example.com', OTP_DRY_RUN: undefined });
    const link = seed(raw);
    expect((await app.request(link.url, {}, env)).status).toBe(404);
  });

  it('does not exist without the local dry-run switch', async () => {
    const { app, env, raw } = setup({ OTP_DRY_RUN: undefined });
    const link = seed(raw);
    expect((await app.request(link.url, {}, env)).status).toBe(404);
  });

  it('only answers on a loopback host', async () => {
    const { app, env, raw } = setup();
    const link = seed(raw);
    const res = await app.request(`http://admin.lan:8787${path(link.url)}`, {}, env);
    expect(res.status).toBe(404);
    // …and the link was not spent by the refused request.
    expect((await app.request(link.url, {}, env)).status).toBe(302);
  });
});

describe('newLink', () => {
  it('stores only the hash of the token, with a 10 minute expiry', () => {
    const now = 1_800_000_000_000;
    const link = newLink({ origin: ORIGIN, email: 'Owner@Example.com', now });
    const token = path(link.url).split('/').pop()!;
    expect(token.length).toBeGreaterThanOrEqual(40);
    const insert = link.sql.find((s: string) => s.startsWith('INSERT'))!;
    expect(insert).not.toContain(token);
    expect(insert).toContain(`'owner@example.com'`);
    expect(insert).toContain(String(now + 10 * 60 * 1000));
  });

  it('rejects an address that could break out of the SQL', () => {
    expect(() => newLink({ origin: ORIGIN, email: "x'@example.com" })).toThrow(/e-mail/);
  });
});
