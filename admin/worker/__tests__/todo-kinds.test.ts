import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

describe('work kinds and parent rules', () => {
  it('creates todos by default and a case with its fields; the kind never changes', async () => {
    const { call, create, raw } = await backlogApp();
    expect((await create()).kind).toBe('todo');
    const kase = await call('POST', '/tasks', { kind: 'case', title: 'Tax', idem_key: 'c', case: { goal: 'Filed', review_every: 7 } });
    expect(kase.status).toBe(201);
    expect(kase.body).toMatchObject({ kind: 'case', case: { goal: 'Filed', review_every: 7, confirmed_at: null } });
    expect((await call('PATCH', `/tasks/${kase.body.id}`, { set: { kind: 'todo' }, expected_rev: 1 })).status).toBe(422);
    expect((await call('POST', '/tasks', { kind: 'thing', title: 'x', idem_key: 'k' })).status).toBe(422);
    expect((await call('POST', '/tasks', { title: 'x', idem_key: 'k2', case: { goal: 'g' } })).status).toBe(422);
    expect(raw.prepare('SELECT count(*) AS n FROM todo_case').get()).toEqual({ n: 1 });
  });
  it('refuses repeat_rule on a case, on create and on PATCH', async () => {
    const { call } = await backlogApp();
    const bad = await call('POST', '/tasks', { kind: 'case', title: 'Rent', idem_key: 'r', due_date: '2026-12-01', repeat_rule: 'monthly:1' });
    expect(bad.status).toBe(422); expect(bad.body.error).toMatch(/cases plugin/);
    const kase = (await call('POST', '/tasks', { kind: 'case', title: 'Rent', idem_key: 'r2', due_date: '2026-12-01' })).body;
    expect((await call('PATCH', `/tasks/${kase.id}`, { set: { repeat_rule: 'monthly:1' }, expected_rev: 1 })).status).toBe(422);
  });
  it('edits case fields through PATCH, only on a case, validating them', async () => {
    const { call, create } = await backlogApp();
    const kase = (await call('POST', '/tasks', { kind: 'case', title: 'C', idem_key: 'c' })).body;
    const res = await call('PATCH', `/tasks/${kase.id}`, { case: { next_action: 'Call', waiting_on: 'Minta Péter' }, expected_rev: 1 });
    expect(res.body).toMatchObject({ rev: 2, case: { next_action: 'Call', waiting_on: 'Minta Péter' } });
    expect((await call('PATCH', `/tasks/${kase.id}`, { case: { review_every: 0 }, expected_rev: 2 })).status).toBe(422);
    expect((await call('PATCH', `/tasks/${kase.id}`, { case: { mood: 'x' }, expected_rev: 2 })).status).toBe(422);
    const todo = await create();
    expect((await call('PATCH', `/tasks/${todo.id}`, { case: { goal: 'x' }, expected_rev: 1 })).status).toBe(422);
  });
  it('enforces parent kinds on create and on move', async () => {
    const { call, create, item, human } = await backlogApp();
    const todo = await create(), kase = (await call('POST', '/tasks', { kind: 'case', title: 'C', idem_key: 'c' })).body, it1 = await item();
    for (const parent of [todo.id, kase.id, it1.id]) expect((await create({ parent_id: parent })).parent_id).toBe(parent);
    for (const parent of [todo.id, kase.id]) {
      expect((await call('POST', '/tasks', { kind: 'case', title: 'C', parent_id: parent, idem_key: crypto.randomUUID() })).status).toBe(422);
      expect((await call('POST', '/items', { project: 'WEB', title: 'I', parent, idem_key: crypto.randomUUID() })).status).toBe(422);
    }
    expect((await item({ parent: it1.id })).parent_id).toBe(it1.id);
    await call('POST', '/projects', { prefix: 'OPS', name: 'C', idem_key: 'ops' }, human);
    expect((await call('POST', '/items', { project: 'OPS', title: 'I', parent: it1.id, idem_key: 'x' })).status).toBe(422);
    const move = (id: string, parent_id: string | null, rev: number) => call('POST', `/tasks/${id}/move`, { parent_id, expected_rev: rev });
    expect((await move(kase.id, todo.id, 1)).status).toBe(422);
    expect((await move(it1.id, todo.id, it1.rev)).status).toBe(422);
    const it2 = await item();
    expect((await move(it2.id, it1.id, it2.rev)).status).toBe(200);
    expect((await move(todo.id, it1.id, 1)).status).toBe(200);
  });
  it('GET /me returns the caller, and principals can carry an about line', async () => {
    const { call, human } = await backlogApp();
    expect((await call('GET', '/me')).body).toMatchObject({ id: 'a', handle: 'a' });
    expect((await call('GET', '/me', undefined, human)).body).toMatchObject({ kind: 'human', handle: 'owner' });
    expect((await call('GET', '/me', undefined, { 'X-Mentat-Token': 'nobody' })).status).toBe(403);
  });
});
