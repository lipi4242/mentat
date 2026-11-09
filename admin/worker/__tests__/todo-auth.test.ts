import { describe, expect, it } from 'vitest';
import app from '../src/index';
import { todoApp } from './todo-fixture';
import { signIn } from './sign-in';

describe('todo auth and principal bootstrap', () => {
  it.each(['todo:read','todo:writeall','other:write'])('rejects insufficient scope %s', async scope => {
    const { call } = await todoApp(scope); expect((await call('GET', '/tasks')).status).toBe(403);
  });
  it('rejects unknown, expired, unmapped and disabled agents', async () => {
    const { call, raw } = await todoApp();
    // Unknown and expired tokens fail in the shared guard: 401, like every plugin.
    expect((await call('GET', '/tasks', undefined, { 'X-Mentat-Token': 'unknown' })).status).toBe(401);
    raw.prepare("UPDATE agent_token SET expires_at='2000-01-01' WHERE id='a'").run();
    expect((await call('GET', '/tasks')).status).toBe(401);
    raw.prepare("DELETE FROM todo_principal WHERE id='b'").run();
    expect((await call('GET', '/tasks', undefined, { 'X-Mentat-Token': 'b' })).status).toBe(403);
    raw.prepare("UPDATE todo_principal SET disabled_at='2026-01-01' WHERE id='c'").run();
    expect((await call('GET', '/tasks', undefined, { 'X-Mentat-Token': 'c' })).status).toBe(403);
    expect((await call('GET', '/tasks', undefined, {})).status).toBe(401);
  });
  it('bootstrap only maps the session owner and agents cannot create principals', async () => {
    const { call, env, count } = await todoApp();
    env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
    env.OTP_SENDER = 'Mentat <noreply@example.com>';
    const cookie = (await signIn(app, env, 'owner@example.com'))!;
    const h = { cookie };
    const human = { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' };
    expect((await call('GET', '/tasks', undefined, h)).status).toBe(403);
    expect((await call('POST', '/principals', { ...human, auth_email: 'other@example.com' }, h)).status).toBe(403);
    expect((await call('POST', '/principals', human)).status).toBe(403);
    expect((await call('POST', '/principals', human, h)).status).toBe(201);
    expect((await call('POST', '/principals', human, h)).status).toBe(200);
    expect(count()).toBe(1);
    expect((await call('GET', '/tasks', undefined, h)).status).toBe(200);
    expect((await call('GET', '/tasks', undefined, { ...h, 'X-Mentat-Token': 'unknown' })).status).toBe(401);
    expect((await call('POST', '/tasks', { title: 'Human task', idem_key: 'human' }, h)).status).toBe(201);
  });
  it('stores the agent profile image data URI at principal setup and returns it with comments', async () => {
    const { call, env, raw, create } = await todoApp();
    env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
    env.OTP_SENDER = 'Mentat <noreply@example.com>';
    const cookie = (await signIn(app, env, 'owner@example.com'))!;
    await call('POST', '/principals', { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' }, { cookie });
    raw.prepare("DELETE FROM todo_principal WHERE id='c'").run();
    const avatar = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5XcAAAAASUVORK5CYII=';
    const body = { kind: 'agent', agent_token_id: 'c', handle: 'bot', display_name: 'Bot', avatar, idem_key: 'bot' };
    expect((await call('POST', '/principals', body, { cookie })).body.avatar).toBe(avatar);
    const task = await create();
    await call('POST', `/tasks/${task.id}/comments`, { body: 'Hello', expected_rev: 1 }, { 'X-Mentat-Token': 'c' });
    expect((await call('GET', `/tasks/${task.id}`)).body.comments[0]).toMatchObject({ display_name: 'Bot', handle: 'bot', kind: 'agent', avatar });
  });
});
