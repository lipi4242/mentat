// A one-off date inside a series (mérés 11): the gas bill is paid by the 10th
// from now on, but October's 10th has passed, so October is due on the 20th.
// October stays an occurrence of the monthly:10 series — anchor 2026-10-10,
// due_at 2026-10-20 — instead of a separate one-off case, so "befizettem"
// closes the series' October and the series' history starts at its anchor.
import { describe, it, expect } from 'vitest';
import { casesApp, gasBill, GAS } from './cases-fixture';

const october = { ...gasBill, due_at: '2026-10-20' };

describe('a moved due date of the current occurrence', () => {
  it('keeps the series and shows the moved date as the open occurrence', async () => {
    const { put, call } = await casesApp();
    const res = await put(GAS, october);
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ recurrence: 'monthly:10', anchor_at: '2026-10-10', due_at: '2026-10-20' });
    const due = await call('GET', '/api/cases/due?until=2026-11-10');
    expect(due.body.map((o: any) => [o.due_at, o.closable])).toEqual([
      ['2026-10-20', true],
      ['2026-11-10', false],
    ]);
    expect((await call('GET', '/api/cases/due?until=2026-10-19')).body).toEqual([]);
  });

  it.each([['the moved date', '2026-10-20'], ['the series date', '2026-10-10']])(
    'closing by %s closes the series October; due_at moves to 11-10',
    async (_l, day) => {
      const { put, close, count } = await casesApp();
      await put(GAS, october);
      const res = await close(GAS, { due_at: day });
      expect(res.status).toBe(200);
      expect(res.body).toMatchObject({ due_at: '2026-11-10', status: 'open' });
      expect(res.body.occurrences.map((o: any) => o.due_at)).toEqual(['2026-10-10']);
      for (const again of ['2026-10-20', '2026-10-10']) {
        expect((await close(GAS, { due_at: again })).body).toMatchObject({ already_closed: true, due_at: '2026-11-10' });
      }
      expect(count('cases_occurrence')).toBe(1);
    },
  );

  it('refuses a later month while the moved October is open', async () => {
    const { put, close, count } = await casesApp();
    await put(GAS, october);
    const res = await close(GAS, { due_at: '2026-12-10' });
    expect(res.status).toBe(409);
    expect(res.body).toMatchObject({ earliest_open: '2026-10-20' });
    expect((await close(GAS, { due_at: '2026-10-25' })).status).toBe(422);
    expect(count('cases_occurrence')).toBe(0);
  });

  it('keeps the moved date through an unrelated edit', async () => {
    const { put } = await casesApp();
    await put(GAS, october);
    const res = await put(GAS, { next_action: 'Átutalni', version: 1 });
    expect(res.body).toMatchObject({ due_at: '2026-10-20', version: 2 });
  });

  it('turns an existing monthly:20 case into monthly:10 with October on the 20th', async () => {
    const { put, close } = await casesApp();
    await put(GAS, { ...gasBill, recurrence: 'monthly:20', anchor_at: '2026-10-20' });
    const res = await put(GAS, { recurrence: 'monthly:10', anchor_at: '2026-10-10', due_at: '2026-10-20', version: 1 });
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ anchor_at: '2026-10-10', due_at: '2026-10-20' });
    expect((await close(GAS, { due_at: '2026-10-20' })).body.occurrences.map((o: any) => o.due_at)).toEqual(['2026-10-10']);
  });

  it.each([
    ['before the occurrence', '2026-10-05'],
    ['on the next occurrence', '2026-11-10'],
    ['past the next occurrence', '2026-11-20'],
  ])('422s a due_at %s, naming the allowed range', async (_l, due_at) => {
    const { put } = await casesApp();
    const res = await put(GAS, { ...gasBill, due_at });
    expect(res.status).toBe(422);
    expect(res.body.error).toMatch(/2026-10-10.*2026-11-10/);
  });
});
