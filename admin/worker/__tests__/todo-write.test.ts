import { describe, expect, it } from 'vitest';
import { todoApp } from './todo-fixture';

describe('todo revisions and atomic writes', () => {
  it('creates idempotently with first payload winning and no second event', async () => {
    const { call, count } = await todoApp();
    const first = await call('POST', '/tasks', { title: 'First', idem_key: 'key' });
    const retry = await call('POST', '/tasks', { title: 'Different', idem_key: 'key' });
    expect(first.status).toBe(201); expect(retry.status).toBe(200);
    expect(retry.body).toEqual(first.body); expect(count()).toBe(1);
    expect(first.body.id).toMatch(/^[0-7][0-9A-HJKMNP-TV-Z]{25}$/);
  });
  it('requires expected_rev, returns current, and preserves events on conflict', async () => {
    const { create, call, count } = await todoApp(); const row = await create();
    expect((await call('PATCH', `/tasks/${row.id}`, { set: { title: 'Updated' }, expected_rev: 1 })).body.rev).toBe(2);
    for (const expected_rev of [undefined, 1]) {
      const res = await call('PATCH', `/tasks/${row.id}`, { set: { title: 'Lost' }, expected_rev });
      expect(res.status).toBe(409); expect(res.body.current.title).toBe('Updated');
    }
    expect(count()).toBe(2);
  });
  it('does not append an event when a writer races after the read', async () => {
    const { create, call, count, raw, env } = await todoApp(); const row = await create();
    const batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      raw.prepare('UPDATE todo_task SET rev=rev+1 WHERE id=?').run(row.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    const res = await call('POST', `/tasks/${row.id}/comments`, { body: '@b hello', expected_rev: 1 });
    expect(res.status).toBe(409); expect(count()).toBe(1); expect(count('todo_comment')).toBe(0); expect(count('todo_mention')).toBe(0);
  });
  it('rolls back the event and task when a related insert fails', async () => {
    const { create, call, count, raw } = await todoApp(); const row = await create();
    raw.exec(`CREATE TRIGGER reject_comment BEFORE INSERT ON todo_comment BEGIN SELECT RAISE(ABORT,'test failure'); END;`);
    expect((await call('POST', `/tasks/${row.id}/comments`, { body: 'hello', expected_rev: 1 })).status).toBe(500);
    expect(count()).toBe(1); expect((await call('GET', `/tasks/${row.id}`)).body.rev).toBe(1);
  });
  it('clears assignment on handback, restricts caller, retains owner and open status', async () => {
    const { create, call } = await todoApp(); const row = await create({ owner_id: 'b', assignee_id: 'a', assignee_note: 'Step' });
    const path = `/tasks/${row.id}/handback`;
    expect((await call('POST', path, { expected_rev: 1 }, { 'X-Mentat-Token': 'b' })).status).toBe(403);
    expect((await call('POST', path, { expected_rev: 1, note: 'Ready' })).body).toMatchObject({ owner_id: 'b', status: 'open', assignee_id: null, assignee_note: null, rev: 2 });
  });
  it('completes once and forbids bypass through PATCH', async () => {
    const { create, call } = await todoApp(); const row = await create({ assignee_id: 'b' });
    expect((await call('PATCH', `/tasks/${row.id}`, { set: { status: 'done' }, expected_rev: 1 })).status).toBe(422);
    const res = await call('POST', `/tasks/${row.id}/complete`, { expected_rev: 1 });
    expect(res.body).toMatchObject({ status: 'done', assignee_id: null, done_by: 'a', rev: 2 });
  });
  it('allows the assignee to complete the whole task while retaining its owner', async () => {
    const { create, call } = await todoApp();
    const row = await create({ owner_id: 'b', assignee_id: 'a', assignee_note: 'Step' });
    expect((await call('POST', `/tasks/${row.id}/complete`, { expected_rev: 1 })).body)
      .toMatchObject({ owner_id: 'b', status: 'done', assignee_id: null, assignee_note: null, done_by: 'a' });
  });
  it('accepts month intervals through create and patch validation', async () => {
    const { call } = await todoApp();
    const created = await call('POST', '/tasks', { title: 'Quarterly', idem_key: 'months', due_date: '2026-01-31', repeat_rule: 'every:3:months' });
    expect(created.status).toBe(201);
    const path = `/tasks/${created.body.id}`;
    expect((await call('PATCH', path, { set: { repeat_rule: 'every:2:months' }, expected_rev: 1 })).body.repeat_rule).toBe('every:2:months');
    expect((await call('PATCH', path, { set: { repeat_rule: 'every:0:months' }, expected_rev: 2 })).status).toBe(422);
  });
  it.each([{ due_date: '2026-02-30' }, { repeat_rule: 'daily' }, { owner_id: 'unknown' }, { assignee_id: '' }, { tz: 'bad/tz' }, { due_time: '29:00' }, { unexpected: 'x' }])('validates %j', async fields => {
    const { call } = await todoApp();
    expect((await call('POST', '/tasks', { title: 'x', idem_key: 'k', ...fields })).status).toBe(422);
  });
});
