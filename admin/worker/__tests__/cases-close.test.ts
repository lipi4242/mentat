// POST /api/cases/:id/occurrences — close the earliest open occurrence of a
// recurring case. Never a later one, never the same one twice.
import { describe, it, expect } from 'vitest';
import { casesApp, gasBill, GAS, TAX } from './cases-fixture';

describe('closing an occurrence', () => {
  it('closes the earliest open one and moves due_at to the next', async () => {
    const { put, close, raw } = await casesApp();
    await put(GAS, gasBill);
    const res = await close(GAS, { due_at: '2026-10-10', done_at: '2026-10-08', note: 'átutalva' });
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ due_at: '2026-11-10', version: 2, status: 'open' });
    expect(res.body.occurrences).toEqual([
      expect.objectContaining({ due_at: '2026-10-10', status: 'done', done_at: '2026-10-08', note: 'átutalva' }),
    ]);
    const ev = raw.prepare(`SELECT actor, actor_token_id, kind FROM cases_event ORDER BY id DESC LIMIT 1`).get();
    expect(ev).toEqual({ actor: 'agent', actor_token_id: 'tok1', kind: 'occurrence.closed' });
  });

  it('is idempotent: closing the same date twice leaves one row and closes nothing else', async () => {
    const { put, close, count } = await casesApp();
    await put(GAS, gasBill);
    await close(GAS, { due_at: '2026-10-10' });
    const again = await close(GAS, { due_at: '2026-10-10' });
    expect(again.status).toBe(200);
    expect(again.body).toMatchObject({ already_closed: true, due_at: '2026-11-10', version: 2 });
    expect(count('cases_occurrence')).toBe(1);
  });

  it('409s a later occurrence while an earlier one is open, and names the earliest', async () => {
    const { put, close, count } = await casesApp();
    await put(GAS, { ...gasBill, anchor_at: '2026-09-10' });
    const res = await close(GAS, { due_at: '2026-10-10' });
    expect(res.status).toBe(409);
    expect(res.body).toMatchObject({ earliest_open: '2026-09-10' });
    expect(count('cases_occurrence')).toBe(0);
  });

  it('records a skipped month as skipped', async () => {
    const { put, close } = await casesApp();
    await put(GAS, gasBill);
    const res = await close(GAS, { due_at: '2026-10-10', status: 'skipped' });
    expect(res.body.occurrences[0].status).toBe('skipped');
  });

  it('walks a monthly:31 series through a short month', async () => {
    const { put, close } = await casesApp();
    await put(GAS, { ...gasBill, recurrence: 'monthly:31', anchor_at: '2027-01-31' });
    expect((await close(GAS, { due_at: '2027-01-31' })).body.due_at).toBe('2027-02-28');
    expect((await close(GAS, { due_at: '2027-02-28' })).body.due_at).toBe('2027-03-31');
  });

  it.each([
    ['a date off the series', { due_at: '2026-10-11' }, /series/],
    ['a bad date', { due_at: '10/10/2026' }, /due_at/],
    ['a bad status', { due_at: '2026-10-10', status: 'paid' }, /status/],
    ['an unknown field', { due_at: '2026-10-10', amount: 9 }, /amount/],
  ])('422s %s', async (_l, body, msg) => {
    const { put, close } = await casesApp();
    await put(GAS, gasBill);
    const res = await close(GAS, body);
    expect(res.status).toBe(422);
    expect(res.body.error).toMatch(msg);
  });

  it('422s a one-off case (it is closed by status), 404s an unknown one', async () => {
    const { put, close } = await casesApp();
    await put(TAX, { title: 'Adó', due_at: '2027-05-20' });
    expect((await close(TAX, { due_at: '2027-05-20' })).status).toBe(422);
    expect((await close(GAS, { due_at: '2026-10-10' })).status).toBe(404);
  });

  it('needs cases:write', async () => {
    const { close } = await casesApp('cases:read');
    expect((await close(GAS, { due_at: '2026-10-10' })).status).toBe(403);
  });
});

describe('closing a quarterly case (VAT return)', () => {
  const vat = { title: 'ÁFA-bevallás', recurrence: 'quarterly:20', anchor_at: '2026-01-20' };

  it('only the earliest open quarter closes; then due_at moves three months', async () => {
    const { put, close } = await casesApp();
    expect((await put(GAS, vat)).body).toMatchObject({ due_at: '2026-01-20' });
    const ahead = await close(GAS, { due_at: '2026-04-20' });
    expect(ahead.status).toBe(409);
    expect(ahead.body).toMatchObject({ earliest_open: '2026-01-20' });
    expect((await close(GAS, { due_at: '2026-02-20' })).status).toBe(422);
    const ok = await close(GAS, { due_at: '2026-01-20' });
    expect(ok.status).toBe(200);
    expect(ok.body).toMatchObject({ due_at: '2026-04-20', status: 'open' });
  });
});
