import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

describe('backlog review guards', () => {
  it('submit accepts a not_met, but accept refuses it', async () => {
    const { at, act, submit, results, checks, get } = await backlogApp();
    const row = await at('taken');
    const mixed = await results(row.id); mixed[1].verdict = 'not_met';
    expect((await submit(row.id, { results: mixed })).body.stage).toBe('review');
    expect((await act(row.id, 'accept', { checks: await checks(row.id) })).status).toBe(422);
    expect((await get(row.id)).stage).toBe('review');
    const na = await at('taken'); const r = await results(na.id, 'na');
    await submit(na.id, { results: r });
    expect((await act(na.id, 'accept', { checks: await checks(na.id) })).body.stage).toBe('done');
  });
  it('accept needs pm_ok on every result of the current round, once each', async () => {
    const { at, act, checks } = await backlogApp();
    const row = await at('review'), all = await checks(row.id);
    expect((await act(row.id, 'accept', { checks: [all[0]] })).status).toBe(422);
    expect((await act(row.id, 'accept', { checks: [all[0], all[0], all[1]] })).status).toBe(422);
    expect((await act(row.id, 'accept', { checks: [all[0], { ...all[1], pm_ok: false }] })).status).toBe(422);
    expect((await act(row.id, 'accept', { checks: [all[0], { ...all[1], pm_ok: 'yes' }] })).status).toBe(422);
    expect((await act(row.id, 'accept', { checks: [all[0], { ...all[1], pm_ok: 0 }] })).status).toBe(422);
    expect((await act(row.id, 'reject', { checks: all, note: 'n' })).status).toBe(422);
    expect((await act(row.id, 'accept', { checks: all.map((k: any) => ({ ...k, pm_ok: 1 })) })).status).toBe(200);
  });
  it('refuses AC edits in review and in the terminal states, allows them in draft, issued and taken', async () => {
    const { at, call, get } = await backlogApp();
    for (const stage of ['review', 'done', 'dropped', 'hold']) {
      const row = await at(stage), ac = row.acs[0];
      expect((await call('POST', `/items/${row.id}/acs`, { text: 'new', expected_rev: row.rev })).status).toBe(409);
      expect((await call('PATCH', `/acs/${ac.id}`, { text: 'changed', expected_rev: row.rev })).status).toBe(409);
      expect((await call('POST', `/acs/${ac.id}/remove`, { expected_rev: row.rev })).status).toBe(409);
      expect((await get(row.id)).acs.map((a: any) => a.text)).toEqual(['AC one', 'AC two']);
    }
    for (const stage of ['draft', 'issued', 'taken']) {
      const row = await at(stage);
      const added = await call('POST', `/items/${row.id}/acs`, { text: 'AC three', expected_rev: row.rev });
      expect(added.status).toBe(200);
      expect((await call('PATCH', `/acs/${row.acs[0].id}`, { text: 'AC one!', expected_rev: added.body.rev })).status).toBe(200);
      expect((await get(row.id)).acs.map((a: any) => a.text)).toEqual(['AC one!', 'AC two', 'AC three']);
    }
  });
  it('only the PM edits ACs', async () => {
    const { at, call } = await backlogApp();
    const row = await at('taken');
    expect((await call('POST', `/items/${row.id}/acs`, { text: 'mine', expected_rev: row.rev }, { 'X-Mentat-Token': 'b' })).status).toBe(403);
  });
  it('an accept prepared before another write to the item ends in a 409', async () => {
    const { at, act, checks, call, get } = await backlogApp();
    // Any write to the anchor (an AC change, a comment) bumps rev; an older form loses.
    const review = await at('review'), form = await checks(review.id), rev = (await get(review.id)).rev;
    await call('POST', `/tasks/${review.id}/comments`, { body: 'one more thing', expected_rev: rev });
    expect((await call('POST', `/items/${review.id}/accept`, { checks: form, expected_rev: rev })).status).toBe(409);
    expect((await act(review.id, 'accept', { checks: form })).status).toBe(200);
  });
  it('an AC edit racing a submit loses inside the batch', async () => {
    const { at, call, env, raw, get } = await backlogApp();
    const row = await at('taken'), batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      raw.prepare("UPDATE backlog_item SET stage='review' WHERE task_id=?").run(row.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('PATCH', `/acs/${row.acs[0].id}`, { text: 'moved goalpost', expected_rev: row.rev })).status).toBe(409);
    expect((await get(row.id)).acs[0].text).toBe('AC one');
  });
  it('dedupes links and lets PM or developer add them', async () => {
    const { at, call, get } = await backlogApp();
    const row = await at('taken'), url = 'https://github.com/o/r/pull/7';
    const add = async (who: string) => call('POST', `/items/${row.id}/links`, { kind: 'pr', url, expected_rev: (await get(row.id)).rev }, { 'X-Mentat-Token': who });
    expect((await add('b')).status).toBe(200);
    expect((await add('a')).status).toBe(422);
    expect((await add('c')).status).toBe(403);
    const link = (await get(row.id)).links[0];
    expect((await call('POST', `/links/${link.id}/remove`, { expected_rev: (await get(row.id)).rev })).status).toBe(200);
    expect((await add('a')).status).toBe(200);
    const bad = await call('POST', `/items/${row.id}/links`, { kind: 'task', url, expected_rev: (await get(row.id)).rev });
    expect(bad.status).toBe(422);
  });
});
