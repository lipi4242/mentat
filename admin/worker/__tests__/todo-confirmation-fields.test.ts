// The fields that void a case's confirmation live in one named list; an agent's edit of any of them
// clears the confirmation, the title included, and a field off the list (the due date) does not.
import { describe, expect, it } from 'vitest';
import { backlogApp } from './backlog-fixture';
import { CASE_FIELDS, CONFIRMATION_FIELDS } from '../src/plugins/todo/case-fields';

const A = { 'X-Mentat-Token': 'a' };
const EXPECTED = ['title', 'description', 'goal', 'frame', 'next_action', 'waiting_on', 'due_reason', 'brain_ref', 'review_every'];

describe('the confirmation fields', () => {
  it('are named in one list: the task text and every case field', () => {
    expect([...CONFIRMATION_FIELDS].sort()).toEqual([...EXPECTED].sort());
    for (const k of CASE_FIELDS) expect(CONFIRMATION_FIELDS, k).toContain(k);
  });

  it("an agent's edit of each listed field clears the confirmation", async () => {
    const { call, human } = await backlogApp();
    for (const field of EXPECTED) { // the named list, not the code's: a field dropped from the code fails here
      const kase = (await call('POST', '/tasks', { kind: 'case', title: 'Pay the rent', idem_key: `case-${field}` }, A)).body;
      expect((await call('POST', `/tasks/${kase.id}/confirm`, { expected_rev: 1 }, human)).body.case.confirmed_at).toBeTruthy();
      const value = field === 'review_every' ? 30 : `changed ${field}`;
      const edit = ['title', 'description'].includes(field) ? { set: { [field]: value } } : { case: { [field]: value } };
      const res = await call('PATCH', `/tasks/${kase.id}`, { ...edit, expected_rev: 2 }, A);
      expect(res.status, field).toBe(200);
      expect(res.body.case.confirmed_at, field).toBeNull();
    }
  });

  it('a field off the list keeps it', async () => {
    const { call, human } = await backlogApp();
    const kase = (await call('POST', '/tasks', { kind: 'case', title: 'Pay the rent', idem_key: 'case-due' }, A)).body;
    await call('POST', `/tasks/${kase.id}/confirm`, { expected_rev: 1 }, human);
    const res = await call('PATCH', `/tasks/${kase.id}`, { set: { due_date: '2026-12-01' }, expected_rev: 2 }, A);
    expect(res.body.case.confirmed_at).toBeTruthy();
  });
});
