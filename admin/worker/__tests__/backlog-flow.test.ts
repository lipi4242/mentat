import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';

const STAGES = ['draft', 'issued', 'taken', 'review', 'done', 'hold', 'dropped'];
// verb → [allowed from-stages, actor, body]
const VERBS: Record<string, [string[], string, Record<string, unknown>]> = {
  issue: [['draft'], 'a', { dev: 'b' }], take: [['issued'], 'b', {}], handback: [['issued', 'taken'], 'b', { note: 'busy' }],
  submit: [['taken'], 'b', {}], accept: [['review'], 'a', {}], reject: [['review'], 'a', {}],
  hold: [['draft', 'issued', 'taken', 'review'], 'a', {}], resume: [['hold'], 'a', {}],
  drop: [['draft', 'issued', 'taken', 'review', 'hold'], 'a', {}],
};

describe('backlog state machine', () => {
  it('walks draft → issued → taken → review → done with receipts, ball and status', async () => {
    const { item, act, submit, checks, get } = await backlogApp();
    const row = await item();
    expect(row).toMatchObject({ kind: 'item', stage: 'draft', key: 'WEB-1', owner_id: 'a', assignee_id: null, status: 'open' });
    expect((await act(row.id, 'issue', { dev: 'b' })).body).toMatchObject({ stage: 'issued', dev_id: 'b', assignee_id: 'b' });
    expect((await get(row.id)).issued_at).toBeTruthy();
    expect((await act(row.id, 'take', {}, 'b')).body).toMatchObject({ stage: 'taken', assignee_id: 'b' });
    expect((await get(row.id)).taken_at).toBeTruthy();
    expect((await submit(row.id, { head_sha: 'abc1234', links: [{ kind: 'pr', url: 'https://github.com/o/r/pull/1' }] })).body)
      .toMatchObject({ stage: 'review', assignee_id: null });
    const done = await act(row.id, 'accept', { checks: await checks(row.id) });
    expect(done.body).toMatchObject({ stage: 'done', status: 'done', assignee_id: null, done_by: 'a' });
    const detail = await get(row.id);
    expect(detail.reports[0]).toMatchObject({ round: 1, pm_verdict: 'accepted', decided_by: 'a', head_sha: 'abc1234' });
    expect(detail.reports[0].results.map((r: any) => [r.ac_text, r.pm_ok])).toEqual([['AC one', 1], ['AC two', 1]]);
    expect(detail.links).toMatchObject([{ kind: 'pr', url: 'https://github.com/o/r/pull/1' }]);
    expect(detail.events.map((e: any) => e.kind)).toEqual(['created', 'item_issue', 'item_take', 'item_submit', 'item_accept']);
  });
  it('refuses every verb from every stage it does not start from, including both terminal states', async () => {
    const app = await backlogApp();
    for (const stage of STAGES) {
      for (const [verb, [from, who, body]] of Object.entries(VERBS)) {
        if (from.includes(stage)) continue;
        const row = await app.at(stage);
        const res = await app.act(row.id, verb, body, who);
        expect([verb, stage, res.status]).toEqual([verb, stage, 409]);
        expect(res.body.current).toMatchObject({ stage, rev: row.rev });
        expect((await app.get(row.id)).rev).toBe(row.rev);
      }
    }
  });
  it('reject returns the item to the developer and the next submit is a new round', async () => {
    const { at, act, submit, checks, get } = await backlogApp();
    const row = await at('review');
    expect((await act(row.id, 'reject', { checks: await checks(row.id, false) })).status).toBe(422);
    const rejected = await act(row.id, 'reject', { checks: await checks(row.id, false), note: 'AC two is open' });
    expect(rejected.body).toMatchObject({ stage: 'taken', assignee_id: 'b' });
    expect((await get(row.id)).reports[0]).toMatchObject({ pm_verdict: 'rejected', pm_note: 'AC two is open' });
    expect((await get(row.id)).reports[0].results[0]).toMatchObject({ pm_ok: 0, pm_note: 'not yet' });
    expect((await submit(row.id)).body.stage).toBe('review');
    expect((await get(row.id)).reports.map((r: any) => r.round)).toEqual([1, 2]);
  });
  it('hold remembers the stage and resume restores it with the right ball', async () => {
    const { at, act, get } = await backlogApp();
    for (const [stage, ball] of [['draft', null], ['issued', 'b'], ['taken', 'b'], ['review', null]]) {
      const row = await at(stage as string);
      expect((await act(row.id, 'hold', { note: 'pause' })).body).toMatchObject({ stage: 'hold', hold_from: stage, assignee_id: null });
      expect((await act(row.id, 'resume')).body).toMatchObject({ stage, hold_from: null, assignee_id: ball, status: 'open' });
    }
    const held = await at('hold');
    expect((await act(held.id, 'drop', { note: 'stop' })).body).toMatchObject({ stage: 'dropped', status: 'dropped', hold_from: null });
    expect((await get(held.id)).events.at(-1).diff_json).toContain('"note":"stop"');
  });
  it('handback needs a note, returns the item to draft and clears the developer', async () => {
    const { at, act } = await backlogApp();
    const row = await at('taken');
    expect((await act(row.id, 'handback', {}, 'b')).status).toBe(422);
    expect((await act(row.id, 'handback', { note: 'no time' }, 'b')).body).toMatchObject({ stage: 'draft', dev_id: null, assignee_id: null });
  });
  it('issue needs at least one live AC and an enabled developer', async () => {
    const { item, act, raw } = await backlogApp();
    const bare = await item({ acs: [] });
    expect((await act(bare.id, 'issue', { dev: 'b' })).status).toBe(422);
    raw.prepare("UPDATE todo_principal SET disabled_at='2026-01-01' WHERE id='c'").run();
    const row = await item();
    expect((await act(row.id, 'issue', { dev: 'c' })).status).toBe(422);
    expect((await act(row.id, 'issue', { dev: 'nobody' })).status).toBe(422);
    expect((await act(row.id, 'issue', { dev: 'a' })).body).toMatchObject({ stage: 'issued', dev_id: 'a' });
  });
  it('lets a human admin do PM verbs and records the human as the actor', async () => {
    const { item, act, get } = await backlogApp();
    const row = await item();
    expect((await act(row.id, 'issue', { dev: 'b' }, 'human')).status).toBe(200);
    const me = (await get(row.id)).events.at(-1).actor_id;
    expect(me).not.toBe('a');
    expect((await act(row.id, 'take', {}, 'human')).status).toBe(403);
  });
});
