import { describe, expect, it } from 'vitest';
import { todoApp } from './todo-fixture';

describe('todo independent completion and descendant progress', () => {
  it('closing a parent leaves children open, with no child events or revision changes', async () => {
    const { create, call, count } = await todoApp();
    const parent = await create(), child = await create({ parent_id: parent.id });
    const before = count();
    expect((await call('POST', `/tasks/${parent.id}/complete`, { expected_rev: 1 })).body.status).toBe('done');
    expect(count()).toBe(before + 1);
    expect((await call('GET', `/tasks/${child.id}`)).body).toMatchObject({ status: 'open', rev: 1, progress: null });
    expect((await call('GET', `/tasks/${parent.id}`)).body.progress).toEqual({ done: 0, total: 1, percent: 0 });
  });

  it('all children done gives 100% without closing or revising the parent', async () => {
    const { create, call, count } = await todoApp();
    const parent = await create(), child = await create({ parent_id: parent.id });
    const before = count();
    await call('POST', `/tasks/${child.id}/complete`, { expected_rev: 1 });
    expect(count()).toBe(before + 1);
    expect((await call('GET', `/tasks/${parent.id}`)).body).toMatchObject({ status: 'open', rev: 1, progress: { done: 1, total: 1, percent: 100 } });
    await call('PATCH', `/tasks/${child.id}`, { expected_rev: 2, set: { status: 'open' } });
    expect((await call('GET', `/tasks/${parent.id}`)).body.progress).toEqual({ done: 0, total: 1, percent: 0 });
  });

  it('weights leaves equally across levels and ignores internal status and list filters', async () => {
    const { create, call } = await todoApp();
    const root = await create({ due_date: '2026-10-27', owner_id: 'b' });
    const branch = await create({ parent_id: root.id });
    const deep = await create({ parent_id: branch.id });
    const done = await create({ parent_id: deep.id });
    await create({ parent_id: deep.id });
    const direct = await create({ parent_id: root.id });
    for (const task of [branch, done, direct]) await call('POST', `/tasks/${task.id}/complete`, { expected_rev: 1 });
    const detail = (await call('GET', `/tasks/${root.id}`)).body;
    expect(detail.progress).toEqual({ done: 2, total: 3, percent: 67 });
    expect(detail.children.find((r: any) => r.id === branch.id).progress).toEqual({ done: 1, total: 2, percent: 50 });
    const filtered = (await call('GET', '/tasks?root=1&ball=b&status=open&due_before=2026-10-27')).body;
    expect(filtered).toHaveLength(1);
    expect(filtered[0].progress).toEqual(detail.progress);
    expect((await call('GET', `/tasks/${branch.id}`)).body.progress).toEqual({ done: 1, total: 2, percent: 50 });
    await call('POST', `/tasks/${direct.id}/move`, { parent_id: null, expected_rev: 2 });
    expect((await call('GET', `/tasks/${root.id}`)).body.progress).toEqual({ done: 1, total: 2, percent: 50 });
  });

  it('excludes dropped subtrees, includes archived leaves, and defines empty progress', async () => {
    const { create, call } = await todoApp();
    const root = await create(), branch = await create({ parent_id: root.id, status: 'dropped' });
    const excluded = await create({ parent_id: branch.id });
    await call('POST', `/tasks/${excluded.id}/complete`, { expected_rev: 1 });
    expect((await call('GET', `/tasks/${root.id}`)).body.progress).toEqual({ done: 0, total: 0, percent: 0 });
    const leaf = await create({ parent_id: root.id });
    await call('POST', `/tasks/${leaf.id}/complete`, { expected_rev: 1 });
    await call('PATCH', `/tasks/${leaf.id}`, { set: { archived: 1 }, expected_rev: 2 });
    expect((await call('GET', `/tasks/${root.id}`)).body.progress).toEqual({ done: 1, total: 1, percent: 100 });
  });

  it('rolls one recurring row forward and recalculates progress after checklist reset', async () => {
    const { create, call, count, raw } = await todoApp();
    const root = await create({ repeat_rule: 'daily', due_date: '2000-01-01' });
    const child = await create({ parent_id: root.id });
    await call('POST', `/tasks/${child.id}/complete`, { expected_rev: 1 });
    expect((await call('GET', `/tasks/${root.id}`)).body.progress.percent).toBe(100);
    const next = await call('POST', `/tasks/${root.id}/complete`, { expected_rev: 1 });
    expect(next.body).toMatchObject({ id: root.id, status: 'open' });
    expect(count('todo_task')).toBe(2);
    expect((await call('GET', `/tasks/${root.id}`)).body.progress).toEqual({ done: 0, total: 1, percent: 0 });
    const event = raw.prepare("SELECT diff_json FROM todo_event WHERE kind='occurrence_done'").get() as { diff_json: string };
    expect(JSON.parse(event.diff_json)).toMatchObject({ completed_due_date: '2000-01-01', completed_at: expect.any(String) });
  });
});
