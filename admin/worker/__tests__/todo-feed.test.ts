import { describe, expect, it } from 'vitest';
import { todoApp } from './todo-fixture';
import { extractHandles } from '../src/plugins/todo/mentions';

describe('todo mentions and feeds', () => {
  it('polls by handle and inclusive due date, with assignment taking precedence over owner', async () => {
    const { create, call, raw } = await todoApp();
    raw.prepare("UPDATE todo_principal SET handle='my_agent' WHERE id='a'").run();
    const owned = await create({ due_date: '2026-10-27' });
    const assigned = await create({ owner_id: 'b', assignee_id: 'a', due_date: '2026-10-26' });
    await create({ assignee_id: 'b', due_date: '2026-10-27' });
    await create({ due_date: '2026-10-28' });
    await create();
    const rows = (await call('GET', '/tasks?ball=my_agent&due_before=2026-10-27&status=open')).body;
    expect(rows.map((r: any) => r.id).sort()).toEqual([owned.id, assigned.id].sort());
    expect((await call('GET', '/tasks?ball=a')).status).toBe(422);
    expect((await call('GET', '/tasks?due_before=2026-02-30')).status).toBe(422);
    const all = await call('GET', '/tasks', undefined, { 'X-Mentat-Token': 'c' });
    expect(all.body).toHaveLength(5);
    expect((await call('GET', `/tasks/${owned.id}`, undefined, { 'X-Mentat-Token': 'c' })).status).toBe(200);
  });
  it('filters by owner and assignee handles, combinable with status', async () => {
    const { create, call } = await todoApp();
    const aOnly = await create({ owner_id: 'a' });
    const aToB = await create({ owner_id: 'a', assignee_id: 'b' });
    const bOwn = await create({ owner_id: 'b' });
    const ids = async (qs: string) => (await call('GET', `/tasks?${qs}`)).body.map((r: any) => r.id).sort();
    expect(await ids('owner=a')).toEqual([aOnly.id, aToB.id].sort());
    expect(await ids('assignee=b')).toEqual([aToB.id]);
    expect(await ids('assignee=')).toEqual([aOnly.id, bOwn.id].sort());
    expect(await ids('owner=a&assignee=b')).toEqual([aToB.id]);
    await call('POST', `/tasks/${aOnly.id}/complete`, { expected_rev: 1 });
    expect(await ids('owner=a&status=open')).toEqual([aToB.id]);
    expect(await ids('owner=a&status=done')).toEqual([aOnly.id]);
    for (const qs of ['owner=nobody', 'assignee=nobody']) {
      const res = await call('GET', `/tasks?${qs}`);
      expect(res.status).toBe(422);
      expect(res.body.error).toBe(`${qs.split('=')[0]} must be a known handle`);
    }
  });
  it('extracts unique mentions, excludes emails and does not truncate long handles', () => {
    expect(extractHandles('@a @a hi @b, a@c.test and @unknown')).toEqual(['a','b','unknown']);
    expect(extractHandles('@' + 'a'.repeat(65))).toEqual([]);
  });
  it('replaces task mentions, keeps comment mentions and event-time recipients', async () => {
    const { create, call, raw } = await todoApp();
    const task = await create({ description: '@b @b @unknown', assignee_id: 'c' });
    expect(raw.prepare('SELECT principal_id FROM todo_mention').all()).toEqual([{ principal_id: 'b' }]);
    await call('PATCH', `/tasks/${task.id}`, { set: { description: 'none', assignee_id: null }, expected_rev: 1 });
    expect(raw.prepare('SELECT * FROM todo_mention').all()).toEqual([]);
    await call('POST', `/tasks/${task.id}/comments`, { body: 'Hello @b', expected_rev: 2 });
    const feed = (await call('GET', '/changes?for=b&since=0&limit=2')).body;
    expect(feed.map((e: any) => e.kind)).toEqual(['created','updated']);
    expect((await call('GET', `/changes?for=b&since=${feed[1].seq}`)).body.map((e: any) => e.kind)).toEqual(['commented']);
    expect((await call('GET', '/changes?for=c')).body).toHaveLength(2);
    expect((await call('GET', `/tasks/${task.id}`)).body.comments[0]).toMatchObject({ body: 'Hello @b', display_name: 'A' });
  });
  it.each(['since=-1','since=1.5','limit=501','limit=0','for=unknown'])('rejects bad cursor/filter %s', async q => {
    const { call } = await todoApp(); expect((await call('GET', `/changes?${q}`)).status).toBe(422);
  });
  it('creates labels idempotently and checks revision for membership', async () => {
    const { call, create } = await todoApp();
    const label = await call('POST', '/labels', { name: 'Home', color: '#888888', idem_key: 'home' });
    expect(label.status).toBe(201);
    expect((await call('POST', '/labels', { name: 'Other', idem_key: 'home' })).body.id).toBe(label.body.id);
    const task = await create();
    expect((await call('POST', `/tasks/${task.id}/labels`, { label_ids: [label.body.id], expected_rev: 1 })).body.rev).toBe(2);
    expect((await call('GET', `/tasks?label=${label.body.id}&root=1&ball=a&status=open`)).body).toHaveLength(1);
    expect((await call('POST', `/tasks/${task.id}/labels`, { label_ids: [], expected_rev: 1 })).status).toBe(409);
  });
});
