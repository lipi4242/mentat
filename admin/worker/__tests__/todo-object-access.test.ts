// Object-level authorization: a todo:write token is not a key to every task. Agent A cannot change,
// move, complete or take over agent B's task; a confirmed case loses its confirmation when an agent
// rewrites it; and one agent is never both PM and developer of an item it then accepts.
import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

const A = { 'X-Mentat-Token': 'a' }, B = { 'X-Mentat-Token': 'b' };

async function bTask() {
  const app = await backlogApp();
  const row = (await app.call('POST', '/tasks', { title: "B's recurring job", idem_key: 'b-job', description: 'Do X' }, B)).body;
  return { ...app, row };
}

describe("another principal's task", () => {
  it('agent A cannot PATCH, move, complete, relabel, re-depend or take over B\'s task', async () => {
    const { call, row } = await bTask();
    const path = `/tasks/${row.id}`;
    const tries = [
      call('PATCH', path, { set: { description: 'Do Y instead' }, expected_rev: 1 }, A),
      call('PATCH', path, { set: { assignee_id: 'a' }, expected_rev: 1 }, A), // take it over
      call('PATCH', path, { set: { owner_id: 'a' }, expected_rev: 1 }, A),
      call('POST', `${path}/move`, { parent_id: null, expected_rev: 1 }, A),
      call('POST', `${path}/complete`, { expected_rev: 1 }, A),
      call('POST', `${path}/labels`, { label_ids: [], expected_rev: 1 }, A),
      call('POST', `${path}/deps`, { depends_on_id: row.id, remove: true, expected_rev: 1 }, A),
    ];
    for (const res of await Promise.all(tries)) expect(res.status).toBe(403);
    expect((await call('GET', path, undefined, B)).body).toMatchObject({ rev: 1, description: 'Do X', status: 'open', owner_id: 'b', assignee_id: null });
  });

  it('a refused takeover changes nothing, and the complete after it is refused too', async () => {
    const { call, row } = await bTask();
    const path = `/tasks/${row.id}`;
    expect((await call('PATCH', path, { set: { owner_id: 'a' }, expected_rev: 1 }, A)).status).toBe(403);
    expect((await call('PATCH', path, { set: { assignee_id: 'a' }, expected_rev: 1 }, A)).status).toBe(403);
    expect((await call('GET', path, undefined, B)).body).toMatchObject({ rev: 1, owner_id: 'b', assignee_id: null, status: 'open' });
    expect((await call('POST', `${path}/complete`, { expected_rev: 1 }, A)).status).toBe(403);
    expect((await call('GET', path, undefined, B)).body).toMatchObject({ rev: 1, status: 'open', done_by: null });
  });

  it("A cannot create a task in B's name, nor hang a child under B's task", async () => {
    const { call, row } = await bTask();
    expect((await call('POST', '/tasks', { title: 'For B', idem_key: 'k1', owner_id: 'b' }, A)).status).toBe(403);
    expect((await call('POST', '/tasks', { title: 'Child', idem_key: 'k2', parent_id: row.id }, A)).status).toBe(403);
    const delegated = await call('POST', '/tasks', { title: 'Please gate PR 1', idem_key: 'k3', assignee_id: 'b' }, A);
    expect(delegated.body).toMatchObject({ owner_id: 'a', assignee_id: 'b' }); // delegation still works
  });

  it('the owner, the assignee and a human can still act', async () => {
    const { call, human, row } = await bTask();
    const path = `/tasks/${row.id}`;
    expect((await call('PATCH', path, { set: { assignee_id: 'a' }, expected_rev: 1 }, B)).body.assignee_id).toBe('a');
    expect((await call('PATCH', path, { set: { description: 'Do X, carefully' }, expected_rev: 2 }, A)).status).toBe(200);
    expect((await call('PATCH', path, { set: { assignee_id: 'c' }, expected_rev: 3 }, A)).status).toBe(403); // the assignee cannot pass it on
    expect((await call('POST', `${path}/move`, { parent_id: null, expected_rev: 3 }, human)).status).toBe(200);
    expect((await call('POST', `${path}/complete`, { expected_rev: 4 }, A)).body).toMatchObject({ status: 'done', done_by: 'a' });
  });
});

describe('a confirmed case', () => {
  it("an agent's edit of the text clears the confirmation; a human's edit renews it", async () => {
    const { call, human } = await backlogApp();
    const kase = (await call('POST', '/tasks', { kind: 'case', title: 'Pay the rent', idem_key: 'case', description: 'Monthly' }, A)).body;
    const confirmed = (await call('POST', `/tasks/${kase.id}/confirm`, { expected_rev: 1 }, human)).body;
    expect(confirmed.case.confirmed_at).toBeTruthy();
    const dueOnly = await call('PATCH', `/tasks/${kase.id}`, { set: { due_date: '2026-12-01' }, expected_rev: 2 }, A);
    expect(dueOnly.body.case.confirmed_at).toBe(confirmed.case.confirmed_at); // not the text: stays
    const edited = await call('PATCH', `/tasks/${kase.id}`, { set: { description: 'Monthly, to a new account' }, expected_rev: 3 }, A);
    expect(edited.body.case).toMatchObject({ confirmed_at: null, confirmed_by: null });
    const caseField = await call('PATCH', `/tasks/${kase.id}`, { case: { next_action: 'call the bank' }, expected_rev: 4 }, human);
    expect(caseField.body.case.confirmed_at).toBeNull(); // a human edit does not confirm an unconfirmed case
    await call('POST', `/tasks/${kase.id}/confirm`, { expected_rev: 5 }, human);
    const byHuman = await call('PATCH', `/tasks/${kase.id}`, { set: { description: 'Monthly, checked' }, expected_rev: 6 }, human);
    expect(byHuman.body.case.confirmed_at).toBeTruthy();
    expect(byHuman.body.case.confirmed_at).not.toBe(confirmed.case.confirmed_at);
  });
});

describe("another principal's item", () => {
  it('an outsider cannot make itself PM or developer, and its accept after that is refused', async () => {
    const { at, item, act, checks, get, call } = await backlogApp();
    const row = await at('review'); // PM a, dev b
    const before = await get(row.id);
    expect((await call('PATCH', `/items/${row.id}`, { set: { pm: 'c' }, expected_rev: before.rev }, { 'X-Mentat-Token': 'c' })).status).toBe(403);
    const draft = await item(); // PM a, no developer yet
    expect((await act(draft.id, 'issue', { dev: 'c' }, 'c')).status).toBe(403);
    expect(await get(draft.id)).toMatchObject({ owner_id: 'a', dev_id: null, stage: 'draft', rev: draft.rev });
    const after = await get(row.id);
    expect(after).toMatchObject({ owner_id: 'a', dev_id: 'b', stage: 'review', rev: before.rev, title: before.title });
    expect((await act(row.id, 'accept', { checks: await checks(row.id) }, 'c')).status).toBe(403);
    expect((await get(row.id)).stage).toBe('review');
  });
});

describe('author and checker stay apart on an item', () => {
  it('an agent PM cannot issue the item to itself', async () => {
    const { item, act } = await backlogApp();
    const row = await item({}, 'a'); // no default PM: the creator is the PM
    expect(row.owner_id).toBe('a');
    expect((await act(row.id, 'issue', { dev: 'a' }, 'a')).status).toBe(403);
  });

  it('a developer who becomes the PM still cannot accept or reject its own work', async () => {
    const { at, act, checks, get, call } = await backlogApp();
    const row = await at('review'); // PM a, dev b, submitted by b
    const moved = await call('PATCH', `/items/${row.id}`, { set: { pm: 'b' }, expected_rev: (await get(row.id)).rev }, A);
    expect(moved.body.owner_id).toBe('b');
    expect((await act(row.id, 'accept', { checks: await checks(row.id) }, 'b')).status).toBe(403);
    expect((await act(row.id, 'reject', { checks: await checks(row.id, false) }, 'b')).status).toBe(403);
    expect((await get(row.id)).stage).toBe('review');
  });
});
