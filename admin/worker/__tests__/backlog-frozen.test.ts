import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

async function importer() {
  const app = await backlogApp();
  app.raw.prepare("UPDATE agent_token SET scopes = 'todo:write todo:import' WHERE id = 'c'").run();
  const imp = (body: Record<string, unknown>) => app.call('POST', '/items/import', {
    ext_ref: 'linear:u1', project: 'WEB', number: 50, title: 'Imported', stage: 'taken', dev: 'b', idem_key: 'imp-1',
    acs: [{ source_id: 'linear:u1:ac:1', text: 'one' }], ...body }, { 'X-Mentat-Token': 'c' });
  return { ...app, imp };
}

describe('the AC set a PM accepts is the set the developer reported on', () => {
  it('an import rerun skips new ACs once the item is in review, and says so', async () => {
    const { imp, get, submit, act, checks } = await importer();
    const id = (await imp({})).body.id;
    await submit(id);
    const rerun = await imp({ acs: [{ source_id: 'linear:u1:ac:1', text: 'one' }, { source_id: 'linear:u1:ac:2', text: 'two' }] });
    expect(rerun.body).toMatchObject({ created: false, added: { acs: 0 }, skipped: { acs: 1 } });
    expect((await get(id)).acs.map((a: any) => a.text)).toEqual(['one']);
    expect((await act(id, 'accept', { checks: await checks(id) }, 'c')).body.stage).toBe('done');
  });
  it('an import rerun still adds a new AC while the item is editable', async () => {
    const { imp, get } = await importer();
    const id = (await imp({})).body.id;
    const rerun = await imp({ acs: [{ source_id: 'linear:u1:ac:1', text: 'one' }, { source_id: 'linear:u1:ac:2', text: 'two' }] });
    expect(rerun.body).toMatchObject({ added: { acs: 1 }, skipped: { acs: 0 } });
    expect((await get(id)).acs).toHaveLength(2);
  });
  it('accept fails when the report no longer covers every live AC', async () => {
    const { at, act, checks, raw, get } = await backlogApp();
    const row = await at('review');
    // Any future path that slips an AC in after submit: the accept must not pass it unread.
    raw.prepare("INSERT INTO backlog_ac (id,item_id,position,text,created_by,created_at) VALUES ('late',?,'Z','late AC','a','2026-01-01')").run(row.id);
    const res = await act(row.id, 'accept', { checks: await checks(row.id) });
    expect(res.status).toBe(409); expect(res.body.current.stage).toBe('review');
    expect((await get(row.id)).stage).toBe('review');
    expect((await act(row.id, 'reject', { checks: (await checks(row.id, false)), note: 'resubmit' })).body.stage).toBe('taken');
  });
  it('the coverage check also runs inside the accept batch', async () => {
    const { at, call, checks, env, raw, get } = await backlogApp();
    const row = await at('review'), form = await checks(row.id), batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      raw.prepare("INSERT INTO backlog_ac (id,item_id,position,text,created_by,created_at) VALUES ('late',?,'Z','late AC','a','2026-01-01')").run(row.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('POST', `/items/${row.id}/accept`, { checks: form, expected_rev: row.rev })).status).toBe(409);
    expect((await get(row.id)).stage).toBe('review');
  });
  it('submit needs at least one live AC', async () => {
    const { at, act, call, get } = await backlogApp();
    const row = await at('taken');
    for (const ac of row.acs) await call('POST', `/acs/${ac.id}/remove`, { expected_rev: (await get(row.id)).rev });
    const res = await act(row.id, 'submit', { round: 1, summary: 's', results: [] }, 'b');
    expect(res.status).toBe(422);
    expect((await get(row.id))).toMatchObject({ stage: 'taken', reports: [] });
  });
  it('an import rerun never brings back a label removed in Mentat', async () => {
    const { imp, get, call } = await importer();
    const id = (await imp({ labels: ['bug'] })).body.id;
    expect((await get(id)).labels.map((l: any) => l.name)).toEqual(['bug']);
    await call('POST', `/tasks/${id}/labels`, { label_ids: [], expected_rev: (await get(id)).rev });
    expect((await imp({ labels: ['bug', 'new'] })).body.added.labels).toBe(0);
    expect((await get(id)).labels).toEqual([]);
  });
  it('caps ACs at 200 on create, add and import', async () => {
    const { imp, call, get, item } = await importer();
    const texts = (n: number) => Array.from({ length: n }, (_, i) => `ac ${i}`);
    expect((await call('POST', '/items', { project: 'WEB', title: 't', acs: texts(201), idem_key: 'big' })).status).toBe(422);
    const full = await item({ acs: texts(200) });
    expect(full.key).toBeTruthy();
    expect((await call('POST', `/items/${full.id}/acs`, { text: 'one more', expected_rev: (await get(full.id)).rev })).status).toBe(422);
    const acs = texts(201).map((text, i) => ({ source_id: `s${i}`, text }));
    expect((await imp({ acs })).status).toBe(422);
  });
});
