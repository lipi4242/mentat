import { describe, expect, it } from 'vitest';
import { todoApp } from './todo-fixture';

describe('todo trees and dependencies', () => {
  it('rejects self and descendant moves but allows moving to root', async () => {
    const { call, create } = await todoApp(); const a = await create(), b = await create({ parent_id: a.id }), c = await create({ parent_id: b.id });
    for (const parent_id of [a.id, b.id, c.id]) expect((await call('POST', `/tasks/${a.id}/move`, { parent_id, expected_rev: 1 })).status).toBe(422);
    expect((await call('POST', `/tasks/${c.id}/move`, { parent_id: null, position: 'A', expected_rev: 1 })).body).toMatchObject({ parent_id: null, position: 'A', rev: 2 });
    expect((await call('PATCH', `/tasks/${a.id}`, { set: { parent_id: c.id }, expected_rev: 1 })).status).toBe(422);
  });
  it('rechecks graph inside the transaction against concurrent inverse moves', async () => {
    const { call, create, env, raw, count } = await todoApp(); const a = await create(), b = await create();
    const batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      raw.prepare('UPDATE todo_task SET parent_id=?,rev=rev+1 WHERE id=?').run(a.id, b.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('POST', `/tasks/${a.id}/move`, { parent_id: b.id, expected_rev: 1 })).status).toBe(409);
    expect(count()).toBe(2);
    expect((await call('GET', `/tasks/${a.id}`)).body.parent_id).toBeNull();
  });
  it('rejects dependency cycles and supports guarded removal', async () => {
    const { call, create } = await todoApp(); const a = await create(), b = await create(), c = await create();
    for (const [task, dep] of [[a,b],[b,c]]) expect((await call('POST', `/tasks/${task.id}/deps`, { depends_on_id: dep.id, expected_rev: 1 })).status).toBe(200);
    expect((await call('POST', `/tasks/${c.id}/deps`, { depends_on_id: a.id, expected_rev: 1 })).status).toBe(422);
    expect((await call('POST', `/tasks/${a.id}/deps`, { depends_on_id: b.id, remove: true, expected_rev: 2 })).status).toBe(200);
    expect((await call('GET', `/tasks/${a.id}`)).body.deps).toEqual([]);
  });
  it('rollover resets deep completed children with revisions/events, preserves dropped branches', async () => {
    const { call, create, count, raw } = await todoApp();
    const root = await create({ repeat_rule: 'daily', due_date: '2000-01-01', assignee_id: 'b' });
    const child = await create({ parent_id: root.id }), grandchild = await create({ parent_id: child.id });
    const dropped = await create({ parent_id: root.id, status: 'dropped' }), kept = await create({ parent_id: dropped.id });
    for (const task of [child, grandchild, kept]) await call('POST', `/tasks/${task.id}/complete`, { expected_rev: 1 });
    const res = await call('POST', `/tasks/${root.id}/complete`, { expected_rev: 1 });
    expect(res.body).toMatchObject({ status: 'open', assignee_id: null, rev: 2 }); expect(res.body.due_date > new Date().toISOString().slice(0,10)).toBe(true);
    for (const task of [child, grandchild]) expect((await call('GET', `/tasks/${task.id}`)).body).toMatchObject({ status: 'open', rev: 3, done_at: null, done_by: null });
    expect((await call('GET', `/tasks/${kept.id}`)).body.status).toBe('done');
    expect(raw.prepare("SELECT count(*) n FROM todo_event WHERE kind='checklist_reset'").get()).toEqual({ n: 2 });
    const before = count(); expect((await call('POST', `/tasks/${root.id}/complete`, { expected_rev: 1 })).status).toBe(409); expect(count()).toBe(before);
  });
});
