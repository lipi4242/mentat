import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

const payload = (n: number, extra: Record<string, unknown> = {}) => ({
  ext_ref: `linear:u${n}`, project: 'APP', number: n, title: `Issue ${n}`, description: 'Kész, ha:\n- works',
  priority: 2, estimate: 3, stage: 'draft', dev: null, archived: false, created_at: '2026-01-01T00:00:00Z',
  labels: ['bug'], acs: [{ source_id: `linear:u${n}:ac:1`, text: 'works' }],
  comments: [{ source_system: 'linear', source_id: `c${n}`, body: 'hi', source_author: 'Bob', source_created_at: '2026-02-01T00:00:00Z' }],
  links: [{ kind: 'pr', url: `https://github.com/o/r/pull/${n}`, title: 'PR' }], idem_key: `linear-import:u${n}`, ...extra,
});

async function importer() {
  const app = await backlogApp();
  app.raw.prepare("UPDATE agent_token SET scopes = 'todo:write todo:import' WHERE id = 'c'").run();
  const imp = (body: unknown) => app.call('POST', '/items/import', body, { 'X-Mentat-Token': 'c' });
  expect((await app.call('POST', '/projects', { prefix: 'APP', name: 'Apps', idem_key: 'app' }, { 'X-Mentat-Token': 'c' })).status).toBe(201);
  return { ...app, imp };
}
const rows = (raw: any) => Object.fromEntries(['todo_task', 'backlog_item', 'backlog_ac', 'todo_comment', 'todo_task_label', 'todo_label', 'backlog_link']
  .map(t => [t, (raw.prepare(`SELECT count(*) AS n FROM ${t}`).get() as { n: number }).n]));

describe('Linear import', () => {
  it('a plain agent token gets 403 on every import endpoint and on POST /projects', async () => {
    const { call } = await backlogApp();
    expect((await call('POST', '/items/import', payload(1))).status).toBe(403);
    expect((await call('POST', '/projects', { prefix: 'APP', name: 'J', idem_key: 'j' })).status).toBe(403);
    expect((await call('POST', '/items/import/parent', { ext_ref: 'linear:u1', parent_ext_ref: 'linear:u2' })).status).toBe(403);
    expect((await call('GET', '/me')).status).toBe(200); // a plain todo:write token, nothing more
  });
  it('creates the item with its Linear number, children and provenance in one batch', async () => {
    const { imp, get, call } = await importer();
    const res = await imp(payload(431, { stage: 'taken', dev: 'b' }));
    expect(res.status).toBe(201); expect(res.body).toMatchObject({ key: 'APP-431', created: true });
    const item = await get('app-431');
    expect(item).toMatchObject({ stage: 'taken', dev_id: 'b', assignee_id: 'b', ext_ref: 'linear:u431', priority: 2, created_at: '2026-01-01T00:00:00Z' });
    expect(item.acs).toMatchObject([{ text: 'works', source_id: 'linear:u431:ac:1' }]);
    expect(item.comments[0]).toMatchObject({ author_id: 'c', source_system: 'linear', source_author: 'Bob', source_created_at: '2026-02-01T00:00:00Z' });
    expect(item.labels.map((l: any) => l.name)).toEqual(['bug']);
    expect(item.links).toMatchObject([{ kind: 'pr', url: 'https://github.com/o/r/pull/431' }]);
    expect((await call('POST', '/items', { project: 'APP', title: 'Native', idem_key: 'n' })).body.key).toBe('APP-432');
  });
  it('a rerun duplicates nothing and never overwrites what changed in Mentat', async () => {
    const { imp, raw, call, get, count } = await importer();
    await imp(payload(1)); await imp(payload(2, { stage: 'done', archived: true }));
    const before = rows(raw), events = count();
    const again = await imp(payload(1, { title: 'Renamed in Linear' }));
    expect(again.status).toBe(200); expect(again.body).toMatchObject({ created: false, added: { acs: 0, comments: 0, labels: 0, links: 0 } });
    expect(rows(raw)).toEqual(before); expect(count()).toBe(events);
    const item = await get('APP-1');
    expect(item.title).toBe('Issue 1');
    // The importer is the PM here (the project has no default PM).
    const pm = { 'X-Mentat-Token': 'c' };
    expect((await call('PATCH', `/items/${item.id}`, { set: { title: 'Edited in Mentat' }, expected_rev: item.rev }, pm)).status).toBe(200);
    expect((await call('POST', `/acs/${item.acs[0].id}/remove`, { expected_rev: item.rev + 1 }, pm)).status).toBe(200);
    const more = payload(1, { comments: [...payload(1).comments as unknown[], { source_system: 'linear', source_id: 'c-new', body: 'later' }] });
    expect((await imp(more)).body.added).toEqual({ acs: 0, comments: 1, labels: 0, links: 0 });
    const after = await get('APP-1');
    expect(after.title).toBe('Edited in Mentat'); expect(after.acs).toHaveLength(0); expect(after.comments).toHaveLength(2);
    expect((await get('APP-2'))).toMatchObject({ stage: 'done', status: 'done', archived: 1 });
  });
  it('refuses a number held by a native item, and stages the import cannot create', async () => {
    const { imp, call } = await importer();
    await call('POST', '/items', { project: 'APP', title: 'Native', idem_key: 'n' });
    expect((await imp(payload(1))).status).toBe(409);
    for (const stage of ['issued', 'review', 'hold']) expect((await imp(payload(5, { stage }))).status).toBe(422);
    expect((await imp(payload(5, { stage: 'taken' }))).status).toBe(422);
    expect((await imp(payload(5, { dev: 'b' }))).status).toBe(422);
  });
  it('wires parents in a second pass, fill-only', async () => {
    const { imp, call, get } = await importer();
    await imp(payload(1)); await imp(payload(2)); await imp(payload(3));
    const link = (child: number, parent: number) => call('POST', '/items/import/parent', { ext_ref: `linear:u${child}`, parent_ext_ref: `linear:u${parent}` }, { 'X-Mentat-Token': 'c' });
    expect((await link(2, 1)).status).toBe(200);
    const parent = (await get('APP-1')).id;
    expect((await get('APP-2')).parent_id).toBe(parent);
    expect((await link(2, 3)).body.parent_id).toBe(parent);
    expect((await link(1, 2)).status).toBe(422);
    expect((await link(9, 1)).status).toBe(404);
  });
});
