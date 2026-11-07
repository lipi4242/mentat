// The Python importer's real payloads (fixtures/linear-import-plan.json, kept current by
// engine/release/tests/test_linear_import.py) posted to the real worker routes, no mocks.
import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';
import plan from './fixtures/linear-import-plan.json';

const T = { 'X-Mentat-Token': 'c' };

async function setup() {
  const app = await backlogApp();
  app.raw.prepare("UPDATE agent_token SET scopes = 'todo:write todo:import' WHERE id = 'c'").run();
  expect((await app.call('POST', '/projects', { prefix: 'DEMO', name: 'Demo', idem_key: 'p' }, T)).status).toBe(201);
  const run = async () => {
    const out = [];
    for (const { parent, ...body } of plan as any[]) out.push((await app.call('POST', '/items/import', body, T)));
    for (const { ext_ref, parent } of plan as any[])
      if (parent) expect((await app.call('POST', '/items/import/parent', { ext_ref, parent_ext_ref: `linear:${parent}` }, T)).status).toBe(200);
    return out;
  };
  return { ...app, run };
}
const counts = (raw: any) => Object.fromEntries(['todo_task', 'backlog_item', 'backlog_ac', 'todo_comment', 'backlog_link']
  .map(t => [t, (raw.prepare(`SELECT count(*) AS n FROM ${t}`).get() as { n: number }).n]));

describe('Python importer payloads against the real worker', () => {
  it('imports, then a rerun duplicates nothing', async () => {
    const { run, raw, get } = await setup();
    const first = await run();
    expect(first.map(r => r.status)).toEqual([201, 201, 201, 201, 201]);
    const before = counts(raw);
    expect(before).toMatchObject({ backlog_item: 5, backlog_ac: 3, backlog_link: 1 });
    const second = await run();
    expect(second.map(r => r.status)).toEqual([200, 200, 200, 200, 200]);
    expect(second.every(r => !r.body.created)).toBe(true);
    expect(counts(raw)).toEqual(before);
    expect(await get('DEMO-1')).toMatchObject({ stage: 'taken', dev_id: 'b' });   // In Review -> taken
    expect(await get('DEMO-3')).toMatchObject({ stage: 'done', archived: 1 });
    expect(await get('DEMO-5')).toMatchObject({ stage: 'draft' });                 // unmapped assignee
  });
});
