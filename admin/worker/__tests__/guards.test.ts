import { describe, it, expect, vi } from 'vitest';
import { Hono } from 'hono';
import { makeDb, makeEnv } from './helpers';
import { signIn } from './sign-in';
import { hashToken } from '../src/lib/tokens';
import { resolveAgentToken, requireWriter, hasScope } from '../src/lib/guards';
import type { AppEnv } from '../src/types';

// agent_token.expires_at is NOT NULL (migration 0002_core.sql: "every caller
// must choose an expiry"), so the seed default is a far-future date rather
// than NULL.
const FAR_FUTURE = '2999-01-01T00:00:00Z';

async function seedToken(
  raw: any,
  opts: Partial<{ scopes: string; active: number; expires: string }> = {},
) {
  const plain = 'mentat_test_secret';
  raw
    .prepare(
      `INSERT INTO agent_token (id, label, token_hash, scopes, active, expires_at) VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .run(
      'tok1',
      'agent',
      await hashToken(plain),
      opts.scopes ?? 'purchasing:write',
      opts.active ?? 1,
      opts.expires ?? FAR_FUTURE,
    );
  return plain;
}

/** Minimal app exercising requireWriter without depending on Task 4 routes. */
function writerApp(scope: string) {
  const app = new Hono<AppEnv>();
  app.post('/guarded', async (c) => {
    const denied = await requireWriter(c, scope);
    if (denied) return denied;
    return c.json({ ok: true, actor: c.get('actor') });
  });
  return app;
}

const ADMIN = 'owner@example.com';
const OUTSIDER = 'someone-else@example.com';

describe('resolveAgentToken', () => {
  it('accepts a valid token and records use', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw);
    const tok = await resolveAgentToken(DB, plain);
    expect(tok?.id).toBe('tok1');
    const row = raw.prepare(`SELECT last_used_at FROM agent_token WHERE id='tok1'`).get() as any;
    expect(row.last_used_at).not.toBeNull();
  });

  it('stores only the hash', async () => {
    const { raw } = makeDb();
    const plain = await seedToken(raw);
    const row = raw.prepare(`SELECT token_hash FROM agent_token WHERE id='tok1'`).get() as any;
    expect(row.token_hash).not.toBe(plain);
    expect(row.token_hash).toHaveLength(64);
  });

  it('rejects an unknown, inactive or expired token', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw);
    expect(await resolveAgentToken(DB, 'wrong')).toBeNull();

    raw.prepare(`UPDATE agent_token SET active = 0 WHERE id='tok1'`).run();
    expect(await resolveAgentToken(DB, plain)).toBeNull();

    raw.prepare(`UPDATE agent_token SET active = 1, expires_at = '2000-01-01T00:00:00Z' WHERE id='tok1'`).run();
    expect(await resolveAgentToken(DB, plain)).toBeNull();
  });

  // The expiry check must FAIL CLOSED for anything it cannot read as a date.
  // A JS-side `new Date(x).getTime() < Date.now()` accepts both of these:
  // NaN < now is false, and '' is falsy so a `row.expires_at &&` guard skips
  // the comparison entirely.
  it.each([
    ['garbage', 'not-a-date'],
    ['empty string', ''],
    ['genuinely expired', '2000-01-01 00:00:00'],
    ['expired, ISO form', '2000-01-01T00:00:00Z'],
  ])('rejects a token whose expires_at is %s', async (_name, expires) => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw);
    raw.prepare(`UPDATE agent_token SET expires_at = ? WHERE id='tok1'`).run(expires);
    expect(await resolveAgentToken(DB, plain)).toBeNull();
  });

  it('accepts both timestamp forms while they are still live', async () => {
    for (const expires of ['2999-01-01 00:00:00', '2999-01-01T00:00:00Z']) {
      const { DB, raw } = makeDb();
      const plain = await seedToken(raw, { expires });
      expect((await resolveAgentToken(DB, plain))?.id).toBe('tok1');
    }
  });

  it('still authorizes when the last_used_at write fails', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw);
    const realPrepare = DB.prepare.bind(DB);
    // last_used_at is telemetry; a write failure must not 500 a valid request.
    const patched = {
      prepare: (sql: string) => {
        if (sql.includes('UPDATE agent_token')) throw new Error('D1_ERROR: transient write failure');
        return realPrepare(sql);
      },
    } as unknown as typeof DB;
    expect((await resolveAgentToken(patched, plain))?.id).toBe('tok1');
  });
});

describe('hasScope', () => {
  it('matches whole whitespace-separated tokens only', () => {
    expect(hasScope('purchasing:write cases:write', 'purchasing:write')).toBe(true);
    expect(hasScope('  purchasing:write\t cases:write ', 'cases:write')).toBe(true);
    // The false positive a naive String.includes() would produce:
    expect(hasScope('purchasing:writeall', 'purchasing:write')).toBe(false);
    expect(hasScope('allpurchasing:write', 'purchasing:write')).toBe(false);
    expect(hasScope('', 'purchasing:write')).toBe(false);
  });
});

describe('requireWriter scope enforcement', () => {
  it('accepts a token that holds the scope and sets the actor', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw, { scopes: 'cases:read purchasing:write' });
    const res = await writerApp('purchasing:write').request(
      '/guarded',
      { method: 'POST', headers: { 'X-Mentat-Token': plain } },
      makeEnv({ DB }),
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, actor: { actor: 'agent', actorTokenId: 'tok1' } });
  });

  it('does NOT let purchasing:writeall satisfy purchasing:write', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw, { scopes: 'purchasing:writeall' });
    const res = await writerApp('purchasing:write').request(
      '/guarded',
      { method: 'POST', headers: { 'X-Mentat-Token': plain } },
      makeEnv({ DB }),
    );
    expect(res.status).toBe(403);
  });

  it('rejects inactive and expired tokens with 401, not 403', async () => {
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw);
    raw.prepare(`UPDATE agent_token SET active = 0 WHERE id='tok1'`).run();
    const inactive = await writerApp('purchasing:write').request(
      '/guarded',
      { method: 'POST', headers: { 'X-Mentat-Token': plain } },
      makeEnv({ DB }),
    );
    expect(inactive.status).toBe(401);

    raw.prepare(`UPDATE agent_token SET active = 1, expires_at = '2000-01-01T00:00:00Z' WHERE id='tok1'`).run();
    const expired = await writerApp('purchasing:write').request(
      '/guarded',
      { method: 'POST', headers: { 'X-Mentat-Token': plain } },
      makeEnv({ DB }),
    );
    expect(expired.status).toBe(401);
  });

  it('rejects an unauthenticated caller with 401', async () => {
    const { DB } = makeDb();
    const res = await writerApp('purchasing:write').request('/guarded', { method: 'POST' }, makeEnv({ DB }));
    expect(res.status).toBe(401);
  });

  it('rejects a token without the required scope', async () => {
    const { default: app } = await import('../src/index');
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw, { scopes: 'cases:read' });
    const res = await app.request(
      '/api/cases/01JAB6Z9Q3M8K7T2V5W4X1Y0RS',
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Mentat-Token': plain },
        body: '{"title":"x"}',
      },
      makeEnv({ DB }),
    );
    expect(res.status).toBe(403);
  });

  it('never lets an agent token reach the auth surface', async () => {
    const { default: app } = await import('../src/index');
    const { DB, raw } = makeDb();
    const plain = await seedToken(raw, { scopes: 'purchasing:write cases:write' });
    const res = await app.request(
      '/api/auth/get-session',
      { headers: { 'X-Mentat-Token': plain } },
      makeEnv({ DB, BETTER_AUTH_SECRET: 'test-secret-not-a-real-one' }),
    );
    // No session is produced from a machine token, whatever the scope string says.
    const body = await res.text();
    expect(body).not.toContain(ADMIN);
    // ...and the handler really ran (rather than erroring out, which would make
    // the assertion above pass for the wrong reason).
    expect(res.status).toBe(200);
    expect(JSON.parse(body)).toBeNull();
  });
});

// The positive control for the negative assertion above. Without this, a
// misconfigured better-auth returning null for EVERYONE would sail through
// the "agent token gets no session" test.
describe('human session (email OTP)', () => {
  it('signs an allowlisted admin in and admits them through requireWriter', async () => {
    const { default: app } = await import('../src/index');
    const { DB } = makeDb();
    const env = makeEnv({ DB, BETTER_AUTH_SECRET: 'test-secret-not-a-real-one' });

    const cookie = await signIn(app, env, ADMIN);
    expect(cookie).toBeTruthy();

    // (a) the session is real and belongs to the allowlisted user
    const sess = await app.request('/api/auth/get-session', { headers: { cookie: cookie! } }, env);
    expect(sess.status).toBe(200);
    expect((await sess.json()) as any).toMatchObject({ user: { email: ADMIN } });

    // (b) requireWriter admits it, with the actor shape the audit trail needs
    const res = await writerApp('purchasing:write').request(
      '/guarded',
      { method: 'POST', headers: { cookie: cookie! } },
      env,
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, actor: { actor: 'user', actorTokenId: null } });
  });

  it('sends no code to a non-allowlisted address, and grants it no session', async () => {
    const { default: app } = await import('../src/index');
    const { DB } = makeDb();
    const env = makeEnv({ DB, BETTER_AUTH_SECRET: 'test-secret-not-a-real-one' });

    // Silent drop: the request is accepted (no user enumeration) but no code
    // is ever sent, so signIn() cannot complete.
    expect(await signIn(app, env, OUTSIDER)).toBeNull();

    const res = await writerApp('purchasing:write').request('/guarded', { method: 'POST' }, env);
    expect(res.status).toBe(401);
  });

  it('refuses to serve the auth surface with no BETTER_AUTH_SECRET', async () => {
    const { default: app } = await import('../src/index');
    const { DB } = makeDb();
    const res = await app.request('/api/auth/get-session', {}, makeEnv({ DB }));
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: 'auth not configured' });
  });
});
