import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

describe('cases: confirmation, review, completion', () => {
  const newCase = async (call: any, who: Record<string, string> | undefined, extra: Record<string, unknown> = {}) =>
    (await call('POST', '/tasks', { kind: 'case', title: 'Case', idem_key: crypto.randomUUID(), ...extra }, who)).body;
  it('a human case is confirmed at creation; an agent case waits for a human confirm', async () => {
    const { call, human } = await backlogApp();
    expect((await newCase(call, human)).case.confirmed_at).toBeTruthy();
    const proposal = await newCase(call, undefined);
    expect(proposal.case.confirmed_at).toBeNull();
    expect((await call('POST', `/tasks/${proposal.id}/confirm`, { expected_rev: 1 })).status).toBe(403);
    const confirmed = await call('POST', `/tasks/${proposal.id}/confirm`, { expected_rev: 1 }, human);
    expect(confirmed.body).toMatchObject({ rev: 2, case: { confirmed_by: expect.any(String) } });
    const again = await call('POST', `/tasks/${proposal.id}/confirm`, { expected_rev: 1 }, human);
    expect(again.status).toBe(200); expect(again.body.rev).toBe(2);
  });
  it('review is for the owner or assignee and stamps last_reviewed', async () => {
    const { call } = await backlogApp();
    const kase = await newCase(call, undefined, { assignee_id: 'b' });
    expect((await call('POST', `/tasks/${kase.id}/review`, { expected_rev: 1 }, { 'X-Mentat-Token': 'c' })).status).toBe(403);
    const res = await call('POST', `/tasks/${kase.id}/review`, { note: 'still waiting', expected_rev: 1 }, { 'X-Mentat-Token': 'b' });
    expect(res.body.case).toMatchObject({ last_reviewed_by: 'b' });
  });
  it('lists confirmed, monitored, open cases due for review, most overdue first', async () => {
    const { call, human, raw } = await backlogApp();
    const old = await newCase(call, human, { owner_id: 'a', case: { review_every: 7 } });
    const older = await newCase(call, human, { owner_id: 'a', case: { review_every: 7 } });
    await newCase(call, human, { owner_id: 'a', case: { review_every: 7 } }); // reviewed recently enough
    const unmonitored = await newCase(call, human, { owner_id: 'a' });
    const proposal = await newCase(call, undefined, { case: { review_every: 1 } });
    const other = await newCase(call, human, { owner_id: 'b', case: { review_every: 1 } });
    const back = (id: string, days: number) => raw.prepare(`UPDATE todo_task SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ','now', ?) WHERE id = ?`).run(`-${days} days`, id);
    for (const [id, d] of [[old.id, 8], [older.id, 20], [unmonitored.id, 30], [proposal.id, 30], [other.id, 30]] as const) back(id, d);
    const due = async (qs = 'for=a') => (await call('GET', `/cases/review-due?${qs}`)).body.map((r: any) => r.id);
    expect(await due()).toEqual([older.id, old.id]);
    await call('POST', `/tasks/${older.id}/review`, { expected_rev: 1 });
    expect(await due()).toEqual([old.id]);
    expect(await due('for=b')).toEqual([other.id]);
    expect((await call('GET', '/cases/review-due?for=nobody')).status).toBe(422);
  });
  it('completing a case with open children needs children: close or keep', async () => {
    const { call, create } = await backlogApp();
    const kase = await newCase(call, undefined);
    const child = await create({ parent_id: kase.id, owner_id: 'b' }), grandchild = await create({ parent_id: child.id });
    const blocked = await call('POST', `/tasks/${kase.id}/complete`, { expected_rev: 1 });
    expect(blocked.status).toBe(409); expect(blocked.body.open_children.sort()).toEqual([child.id, grandchild.id].sort());
    expect((await call('POST', `/tasks/${kase.id}/complete`, { expected_rev: 1, children: 'later' })).status).toBe(422);
    const closed = await call('POST', `/tasks/${kase.id}/complete`, { expected_rev: 1, children: 'close' });
    expect(closed.body.status).toBe('done');
    for (const id of [child.id, grandchild.id]) expect((await call('GET', `/tasks/${id}`)).body).toMatchObject({ status: 'done', rev: 2 });
    const events = (await call('GET', '/changes?for=b')).body.map((e: any) => e.kind);
    expect(events).toContain('completed');
    const kept = await newCase(call, undefined), open = await create({ parent_id: kept.id });
    expect((await call('POST', `/tasks/${kept.id}/complete`, { expected_rev: 1, children: 'keep' })).body.status).toBe('done');
    expect((await call('GET', `/tasks/${open.id}`)).body).toMatchObject({ status: 'open', parent_id: kept.id });
  });
  it('a child created after the check still blocks the completion', async () => {
    const { call, create, env, raw } = await backlogApp();
    const kase = await newCase(call, undefined), batch = env.DB.batch.bind(env.DB);
    let sneaked: any;
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      sneaked = await create({ parent_id: kase.id });
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('POST', `/tasks/${kase.id}/complete`, { expected_rev: 1 })).status).toBe(409);
    expect((raw.prepare('SELECT status FROM todo_task WHERE id = ?').get(kase.id) as any).status).toBe('open');
    expect(sneaked.parent_id).toBe(kase.id);
  });
  it('children applies only to a case', async () => {
    const { call, create } = await backlogApp();
    const todo = await create();
    expect((await call('POST', `/tasks/${todo.id}/complete`, { expected_rev: 1, children: 'close' })).status).toBe(422);
  });
});
