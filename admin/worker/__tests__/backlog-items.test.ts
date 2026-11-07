import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

describe('backlog projects and items', () => {
  it('only a human creates a project; prefixes are validated, unique and idempotent', async () => {
    const { call, human } = await backlogApp();
    expect((await call('POST', '/projects', { prefix: 'OPS', name: 'C', idem_key: 'x' })).status).toBe(403);
    for (const prefix of ['ops', '1AB', 'TOOLONGPX', 'A-B']) expect((await call('POST', '/projects', { prefix, name: 'C', idem_key: prefix }, human)).status).toBe(422);
    expect((await call('POST', '/projects', { prefix: 'WEB', name: 'Dup', idem_key: 'dup' }, human)).status).toBe(422);
    const first = await call('POST', '/projects', { prefix: 'OPS', name: 'Ops', default_pm: 'b', idem_key: 'ops' }, human);
    expect(first.status).toBe(201); expect(first.body.default_pm_id).toBe('b');
    expect((await call('POST', '/projects', { prefix: 'OPS', name: 'Other', idem_key: 'ops' }, human)).body).toEqual(first.body);
    expect((await call('GET', '/projects')).body.map((p: any) => p.prefix)).toEqual(['OPS', 'WEB']);
  });
  it('numbers items per project inside the create batch; a replay allocates nothing', async () => {
    const { call, item, raw } = await backlogApp();
    const one = await item({ idem_key: 'k1' });
    const replay = await call('POST', '/items', { project: 'WEB', title: 'Other', idem_key: 'k1' });
    expect(replay.status).toBe(200); expect(replay.body.id).toBe(one.id);
    expect((await item()).key).toBe('WEB-2');
    raw.exec(`CREATE TRIGGER fail_ac BEFORE INSERT ON backlog_ac BEGIN SELECT RAISE(ABORT,'test failure'); END;`);
    expect((await call('POST', '/items', { project: 'WEB', title: 'Broken', acs: ['x'], idem_key: 'k3' })).status).toBe(500);
    raw.exec('DROP TRIGGER fail_ac');
    expect((await item()).key).toBe('WEB-3');
    expect((await call('POST', '/tasks', { title: 't', idem_key: 'k4' })).status).toBe(201);
    expect((await call('POST', '/items', { project: 'WEB', title: 'x', idem_key: 'k4' })).status).toBe(422);
  });
  it('resolves PREFIX-N in any case, and the PM is pm, else the default PM, else the creator', async () => {
    const { call, item, human } = await backlogApp();
    const mine = await item();
    expect((await call('GET', '/items/web-1')).body.id).toBe(mine.id);
    expect((await call('GET', `/items/${mine.id}`)).body.key).toBe('WEB-1');
    expect((await call('GET', '/items/WEB-99')).status).toBe(404);
    expect(mine.owner_id).toBe('a');
    expect((await item({ pm: 'c' })).owner_id).toBe('c');
    await call('POST', '/projects', { prefix: 'APP', name: 'J', default_pm: 'b', idem_key: 'app' }, human);
    expect((await item({ project: 'app' })).owner_id).toBe('b');
    expect((await call('POST', '/items', { project: 'WEB', title: 'x', pm: 'nobody', idem_key: 'p' })).status).toBe(422);
  });
  it('lists items ranked by position with filters', async () => {
    const { call, at, item } = await backlogApp();
    const draft = await item(), issued = await at('issued');
    const keys = async (qs: string) => (await call('GET', `/items?${qs}`)).body.map((r: any) => r.id);
    expect(await keys('project=WEB')).toEqual([draft.id, issued.id]);
    expect(await keys('stage=issued')).toEqual([issued.id]);
    expect(await keys('dev=b')).toEqual([issued.id]);
    expect(await keys('ball=a')).toEqual([draft.id]);
    expect(await keys('pm=a&stage=draft,issued')).toEqual([draft.id, issued.id]);
    expect(await keys('older_than=1')).toEqual([]);
    for (const qs of ['stage=nope', 'pm=nobody', 'older_than=x', 'project=NOPE']) expect((await call('GET', `/items?${qs}`)).status).toBe(422);
    expect((await call('GET', '/tasks')).body.map((t: any) => t.id)).not.toContain(draft.id);
    expect((await call('GET', '/tasks?kind=item')).body.map((t: any) => t.id)).toEqual([draft.id, issued.id]);
    expect((await call('GET', '/tasks?ball=b&kind=all')).body.map((t: any) => t.id)).toEqual([issued.id]);
  });
  it('older_than counts an issued item from its issue, not from its last comment', async () => {
    const { call, at, raw } = await backlogApp();
    const issued = await at('issued'), draft = await at('draft');
    const ago = "strftime('%Y-%m-%dT%H:%M:%fZ','now','-5 days')";
    raw.prepare(`UPDATE backlog_item SET issued_at = ${ago} WHERE task_id = ?`).run(issued.id);
    raw.prepare(`UPDATE todo_task SET updated_at = ${ago} WHERE id IN (?, ?)`).run(issued.id, draft.id);
    const ids = async (qs: string) => (await call('GET', `/items?${qs}`)).body.map((r: any) => r.id);
    expect(await ids('older_than=3')).toEqual([issued.id, draft.id]);
    for (const id of [issued.id, draft.id]) await call('POST', `/tasks/${id}/comments`, { body: 'any news?', expected_rev: (await call('GET', `/items/${id}`)).body.rev });
    expect(await ids('stage=issued&older_than=3')).toEqual([issued.id]);
    expect(await ids('older_than=3')).toEqual([issued.id]);
  });
  it('PATCH /items edits the spec fields, PM only', async () => {
    const { call, item, get } = await backlogApp();
    const row = await item();
    const set = { title: 'Better', priority: 1, estimate: 3, request_quote: '"fix it"', pm: 'c' };
    expect((await call('PATCH', `/items/${row.id}`, { set, expected_rev: row.rev }, { 'X-Mentat-Token': 'b' })).status).toBe(403);
    expect((await call('PATCH', `/items/${row.id}`, { set: { stage: 'done' }, expected_rev: row.rev })).status).toBe(422);
    expect((await call('PATCH', `/items/${row.id}`, { set: { priority: 9 }, expected_rev: row.rev })).status).toBe(422);
    expect((await call('PATCH', `/items/${row.id}`, { set, expected_rev: row.rev })).body)
      .toMatchObject({ title: 'Better', priority: 1, estimate: 3, request_quote: '"fix it"', owner_id: 'c', stage: 'draft' });
    expect((await get(row.id)).rev).toBe(row.rev + 1);
  });
  it('refuses generic task writes on an item', async () => {
    const { call, at } = await backlogApp();
    const row = await at('issued');
    for (const set of [{ status: 'dropped' }, { assignee_id: 'c' }, { title: 'sneaky' }]) {
      expect((await call('PATCH', `/tasks/${row.id}`, { set, expected_rev: row.rev })).status).toBe(409);
    }
    expect((await call('POST', `/tasks/${row.id}/complete`, { expected_rev: row.rev })).status).toBe(409);
    expect((await call('POST', `/tasks/${row.id}/handback`, { expected_rev: row.rev }, { 'X-Mentat-Token': 'b' })).status).toBe(409);
    expect((await call('POST', '/tasks', { title: 'x', kind: 'item', idem_key: 'i' })).status).toBe(422);
    expect((await call('GET', `/items/${row.id}`)).body).toMatchObject({ stage: 'issued', status: 'open', assignee_id: 'b', rev: row.rev });
  });
});
