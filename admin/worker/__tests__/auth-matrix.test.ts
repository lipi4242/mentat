// One auth decision table, measured on todo AND cases. Both plugins
// decide through lib/guards.ts authorize(), so the same request must get the
// same status on both — a bad token is 401 everywhere, a missing scope 403.
import { describe, expect, it } from 'vitest';
import app from '../src/index';
import { hashToken } from '../src/lib/tokens';
import { signIn } from './sign-in';
import { todoApp } from './todo-fixture';
import { casesApp } from './cases-fixture';

const SECRET = 'test-secret-at-least-thirty-two-characters';
type Call = (headers: Record<string, string>) => Promise<{ status: number; body: any }>;

async function seed(raw: any, id: string, scopes: string, active = 1, expires = '2999-01-01T00:00:00Z') {
  raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,active,expires_at) VALUES (?,?,?,?,?,?)`)
    .run(id, id, await hashToken(`plain-${id}`), scopes, active, expires);
}

/** The same token zoo on every plugin; `ok` is its write scope. */
async function zoo(raw: any, env: any, ok: string) {
  await seed(raw, 'good', ok);
  await seed(raw, 'wrong', `${ok}all other:write`); // substring of the real scope, never a match
  await seed(raw, 'expired', ok, 1, '2000-01-01T00:00:00Z');
  await seed(raw, 'revoked', ok, 0);
  await seed(raw, 'garbage', ok, 1, 'not-a-date');
  env.BETTER_AUTH_SECRET = SECRET;
  env.OTP_SENDER = 'Mentat <noreply@example.com>';
  return (await signIn(app, env, 'owner@example.com'))!;
}

const plugins: Record<string, () => Promise<{ call: Call; env: any; cookie: string }>> = {
  todo: async () => {
    const t = await todoApp();
    const cookie = await zoo(t.raw, t.env, 'todo:write');
    t.raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES ('g','agent','good','Good','good','fixture','good')`).run();
    await t.call('POST', '/principals', { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' }, { cookie });
    return { call: (h) => t.call('GET', '/tasks', undefined, h), env: t.env, cookie };
  },
  cases: async () => {
    const t = await casesApp();
    const cookie = await zoo(t.raw, t.env, 'cases:write');
    return { call: (h) => t.call('GET', '/api/cases', undefined, h), env: t.env, cookie };
  },
};

const tok = (id: string) => ({ 'X-Mentat-Token': `plain-${id}` });

describe.each(Object.keys(plugins))('shared auth decisions on %s', (name) => {
  const rows: [string, (cookie: string) => Record<string, string>, number, string][] = [
    ['no credentials at all', () => ({}), 401, 'unauthorized'],
    ['an unknown token', () => ({ 'X-Mentat-Token': 'nope' }), 401, 'unauthorized'],
    ['an expired token', () => tok('expired'), 401, 'unauthorized'],
    ['a revoked (inactive) token', () => tok('revoked'), 401, 'unauthorized'],
    ['a token with an unparseable expiry', () => tok('garbage'), 401, 'unauthorized'],
    ['an empty token header', () => ({ 'X-Mentat-Token': '' }), 401, 'unauthorized'],
    ['an empty token header next to an admin cookie', (cookie) => ({ cookie, 'X-Mentat-Token': '' }), 401, 'unauthorized'],
    ['a bad token next to an admin cookie (no downgrade)', (cookie) => ({ cookie, 'X-Mentat-Token': 'nope' }), 401, 'unauthorized'],
    ['an expired token next to an admin cookie', (cookie) => ({ cookie, ...tok('expired') }), 401, 'unauthorized'],
    ['a live token without the scope', () => tok('wrong'), 403, 'forbidden'],
    ['a forged cookie', () => ({ cookie: 'better-auth.session_token=forged' }), 401, 'unauthorized'],
  ];
  it.each(rows)('%s', async (_label, headers, status, error) => {
    const { call, cookie } = await plugins[name]();
    const res = await call(headers(cookie));
    expect(res.status).toBe(status);
    expect(res.body.error).toBe(error);
  });

  it('a live scoped token and the admin session both pass', async () => {
    const { call, cookie } = await plugins[name]();
    expect((await call(tok('good'))).status).toBe(200);
    expect((await call({ cookie })).status).toBe(200);
  });

  it('a session whose e-mail left ADMIN_EMAILS is refused', async () => {
    const { call, env, cookie } = await plugins[name]();
    env.ADMIN_EMAILS = 'someone-else@example.com';
    expect((await call({ cookie })).status).toBe(401);
  });

  it('without BETTER_AUTH_SECRET no session counts, tokens still do', async () => {
    const { call, env, cookie } = await plugins[name]();
    delete env.BETTER_AUTH_SECRET;
    expect((await call({ cookie })).status).toBe(401);
    expect((await call(tok('good'))).status).toBe(200);
  });
});

describe('todo principal mapping on top of the shared guard', () => {
  it('a live token with no principal, or a disabled one, is 403 — after the guard said yes', async () => {
    const { call, raw } = await todoApp();
    raw.prepare("DELETE FROM todo_principal WHERE id='b'").run();
    raw.prepare("UPDATE todo_principal SET disabled_at='2026-01-01' WHERE id='c'").run();
    for (const t of ['b', 'c']) {
      const res = await call('GET', '/tasks', undefined, { 'X-Mentat-Token': t });
      expect(res.status).toBe(403);
      expect(res.body.error).toBe('principal is unknown or disabled');
    }
  });

  it('a token acts only as its own principal: body fields cannot switch identity', async () => {
    const { call, create } = await todoApp();
    const task = await create();
    const spoof = await call('POST', `/tasks/${task.id}/comments`, { body: 'hi', expected_rev: 1, created_by: 'a' }, { 'X-Mentat-Token': 'b' });
    expect(spoof.status).toBe(422);
    await call('POST', `/tasks/${task.id}/comments`, { body: 'hi', expected_rev: 1 }, { 'X-Mentat-Token': 'b' });
    expect((await call('GET', `/tasks/${task.id}`)).body.comments[0]).toMatchObject({ handle: 'b' });
  });

  it('an agent token never bootstraps a principal; a todo:write token is not an importer', async () => {
    const { call } = await todoApp();
    const human = { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' };
    expect((await call('POST', '/principals', human)).status).toBe(403);
    expect((await call('POST', '/projects', { prefix: 'APP', name: 'Apps', idem_key: 'app' })).status).toBe(403);
  });
});

describe('/api/meta follows the same header precedence', () => {
  it('an empty or bad token header next to an admin cookie is 401, the cookie alone is 200', async () => {
    const t = await casesApp();
    const cookie = await zoo(t.raw, t.env, 'cases:write');
    expect((await t.call('GET', '/api/meta', undefined, { cookie })).status).toBe(200);
    expect((await t.call('GET', '/api/meta', undefined, { cookie, 'X-Mentat-Token': '' })).status).toBe(401);
    expect((await t.call('GET', '/api/meta', undefined, { cookie, 'X-Mentat-Token': 'nope' })).status).toBe(401);
  });
});
