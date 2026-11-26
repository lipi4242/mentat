// A machine token reads principals without the sign-in e-mail and the token ids; an admin session
// still gets them (the admin UI maps its own principal by e-mail and manages agent tokens).
import { describe, expect, it } from 'vitest';
import app from '../src/index';
import { todoApp } from './todo-fixture';
import { signIn } from './sign-in';

const PRIVATE = ['auth_email', 'agent_token_id'];

async function withOwner() {
  const t = await todoApp();
  t.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  t.env.OTP_SENDER = 'Mentat <noreply@example.com>';
  const cookie = (await signIn(app, t.env, 'owner@example.com'))!;
  await t.call('POST', '/principals', { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' }, { cookie });
  return { ...t, cookie };
}

describe('principal privacy', () => {
  it('an agent token gets no auth_email and no agent_token_id, from /principals or /me', async () => {
    const { call } = await withOwner();
    const list = await call('GET', '/principals');
    expect(list.status).toBe(200);
    expect(list.body.length).toBe(4);
    for (const row of list.body) for (const k of PRIVATE) expect(row).not.toHaveProperty(k);
    expect(JSON.stringify(list.body)).not.toContain('owner@example.com');
    expect(list.body.find((p: any) => p.handle === 'owner')).toMatchObject({ kind: 'human', display_name: 'Owner' });
    const me = await call('GET', '/me');
    expect(me.body).toMatchObject({ id: 'a', handle: 'a' });
    for (const k of PRIVATE) expect(me.body).not.toHaveProperty(k);
  });

  it('an admin session still gets both fields', async () => {
    const { call, cookie } = await withOwner();
    const list = (await call('GET', '/principals', undefined, { cookie })).body;
    expect(list.find((p: any) => p.handle === 'owner').auth_email).toBe('owner@example.com');
    expect(list.find((p: any) => p.handle === 'a').agent_token_id).toBe('a');
    expect((await call('GET', '/me', undefined, { cookie })).body.auth_email).toBe('owner@example.com');
  });
});
