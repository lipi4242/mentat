import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

describe('backlog guards fail closed', () => {
  it('refuses a wrong actor for every role-bound verb', async () => {
    const { at, act, checks } = await backlogApp();
    expect((await act((await at('draft')).id, 'issue', { dev: 'b' }, 'c')).status).toBe(403);
    expect((await act((await at('issued')).id, 'take', {}, 'c')).status).toBe(403);
    expect((await act((await at('issued')).id, 'take', {}, 'a')).status).toBe(403);
    expect((await act((await at('taken')).id, 'handback', { note: 'x' }, 'a')).status).toBe(403);
    const review = await at('review');
    expect((await act(review.id, 'accept', { checks: await checks(review.id) }, 'c')).status).toBe(403);
    expect((await act(review.id, 'reject', { checks: await checks(review.id, false), note: 'n' }, 'c')).status).toBe(403);
    for (const verb of ['hold', 'drop']) expect((await act((await at('draft')).id, verb, {}, 'c')).status).toBe(403);
  });
  it('binds the actor to the token: no request field names another principal', async () => {
    const { at, act, call, get, submit } = await backlogApp();
    const row = await at('taken');
    for (const field of ['actor_id', 'submitted_by', 'author_id', 'principal']) {
      expect((await submit(row.id, { [field]: 'b' }, 'c')).status).toBe(422);
      expect((await act(row.id, 'hold', { [field]: 'a' }, 'c')).status).toBe(422);
    }
    expect((await submit(row.id, {}, 'c')).status).toBe(403);
    expect((await call('POST', `/tasks/${row.id}/comments`, { body: 'hi', author_id: 'a', expected_rev: row.rev }, { 'X-Mentat-Token': 'c' })).status).toBe(422);
    expect((await call('POST', `/tasks/${row.id}/comments`, { body: 'hi', expected_rev: row.rev }, { 'X-Mentat-Token': 'c' })).status).toBe(200);
    const detail = await get(row.id);
    expect(detail.comments.at(-1).author_id).toBe('c');
    expect(detail.events.at(-1).actor_id).toBe('c');
  });
  it('the developer cannot set pm_ok: not in submit, not through accept', async () => {
    const { at, act, results, checks, get } = await backlogApp();
    const row = await at('taken');
    const forged = (await results(row.id)).map((r: any) => ({ ...r, pm_ok: 1 }));
    expect((await act(row.id, 'submit', { round: 1, summary: 's', results: forged }, 'b')).status).toBe(422);
    const review = await at('review');
    expect((await act(review.id, 'accept', { checks: await checks(review.id) }, 'b')).status).toBe(403);
    expect((await get(review.id)).reports[0].results.every((r: any) => r.pm_ok === null)).toBe(true);
  });
  it('refuses a stale rev with the current stage and rev, and writes nothing', async () => {
    const { at, call, count } = await backlogApp();
    const row = await at('issued'); const events = count();
    const res = await call('POST', `/items/${row.id}/take`, { expected_rev: row.rev - 1 }, { 'X-Mentat-Token': 'b' });
    expect(res.status).toBe(409); expect(res.body.current).toMatchObject({ stage: 'issued', rev: row.rev });
    expect(count()).toBe(events);
  });
  it('lets exactly one of two concurrent takes win', async () => {
    const { at, call, env, raw, get } = await backlogApp();
    const row = await at('issued');
    const batch = env.DB.batch.bind(env.DB);
    // The rival wins between our read and our batch: same rev, stage moves on.
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      raw.prepare("UPDATE backlog_item SET stage='taken' WHERE task_id=?").run(row.id);
      raw.prepare('UPDATE todo_task SET rev=rev+1 WHERE id=?').run(row.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    const res = await call('POST', `/items/${row.id}/take`, { expected_rev: row.rev }, { 'X-Mentat-Token': 'b' });
    expect(res.status).toBe(409);
    expect((await get(row.id)).events.filter((e: any) => e.kind === 'item_take')).toHaveLength(0);
  });
  it('refuses a transition whose from-stage changed under the same rev', async () => {
    const { at, call, env, raw, count } = await backlogApp();
    const row = await at('issued'); const events = count();
    const batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      raw.prepare("UPDATE backlog_item SET stage='draft' WHERE task_id=?").run(row.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('POST', `/items/${row.id}/take`, { expected_rev: row.rev }, { 'X-Mentat-Token': 'b' })).status).toBe(409);
    expect(count()).toBe(events);
  });
  it('submit needs exactly the live ACs: missing, duplicate, foreign or removed ids are refused', async () => {
    const { at, item, get, act, results, count, call } = await backlogApp();
    const row = await at('taken'), other = await item();
    const live = await results(row.id), foreign = (await get(other.id)).acs[0].id;
    const send = (r: unknown[]) => act(row.id, 'submit', { round: 1, summary: 's', results: r }, 'b');
    const events = count();
    expect((await send([live[0]])).status).toBe(422);
    expect((await send([live[0], live[0], live[1]])).status).toBe(422);
    expect((await send([...live, { ac_id: foreign, verdict: 'met', evidence: 'e' }])).status).toBe(422);
    expect((await send(live.map((r: any) => ({ ...r, evidence: ' ' })))).status).toBe(422);
    expect(count()).toBe(events);
    // The PM removes AC two while the item is taken; the old form now names a removed AC.
    const removed = live[1].ac_id;
    expect((await call('POST', `/acs/${removed}/remove`, { expected_rev: (await get(row.id)).rev })).status).toBe(200);
    expect((await send(live)).status).toBe(422);
    expect((await send([live[0]])).body.stage).toBe('review');
    expect((await get(row.id)).reports[0].results.map((r: any) => r.ac_id)).toEqual([live[0].ac_id]);
  });
  it('a replayed submit form is a 409, not a second report', async () => {
    const { at, submit, act, results, get } = await backlogApp();
    const row = await at('taken');
    expect((await submit(row.id)).status).toBe(200);
    const res = await act(row.id, 'submit', { round: 1, summary: 's', results: await results(row.id) }, 'b');
    expect(res.status).toBe(409);
    expect((await get(row.id)).reports).toHaveLength(1);
  });
});
