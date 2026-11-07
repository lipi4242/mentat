// Reads: the list, the due window, one case in full, and the change feed.
import { describe, it, expect } from 'vitest';
import { casesApp, gasBill, GAS, TAX, CLAIM } from './cases-fixture';

async function threeCases() {
  const f = await casesApp();
  await f.put(GAS, { ...gasBill, anchor_at: '2026-09-10' });
  await f.put(TAX, { title: 'Adóbevallás', due_at: '2027-05-20' });
  await f.put(CLAIM, { title: 'Kárigény', status: 'waiting', next_action: 'Várunk a biztosítóra', due_at: '2026-10-20' });
  return f;
}

describe('GET /api/cases/due', () => {
  it('lists every open occurrence up to `until`; only the earliest of a case is closable', async () => {
    const { call } = await threeCases();
    const res = await call('GET', '/api/cases/due?until=2026-11-10');
    expect(res.status).toBe(200);
    expect(res.body.map((o: any) => [o.case_id, o.due_at, o.closable])).toEqual([
      [GAS, '2026-09-10', true],
      [GAS, '2026-10-10', false],
      [CLAIM, '2026-10-20', true],
      [GAS, '2026-11-10', false],
    ]);
    expect(res.body[2]).toMatchObject({ title: 'Kárigény', status: 'waiting', next_action: 'Várunk a biztosítóra' });
    expect(res.body[2]).not.toHaveProperty('waiting_on');
  });

  it('leaves out done and dropped cases', async () => {
    const { call, put } = await threeCases();
    await put(CLAIM, { status: 'done', version: 1 });
    const res = await call('GET', '/api/cases/due?until=2026-10-31');
    expect(res.body.map((o: any) => o.case_id)).not.toContain(CLAIM);
  });

  it('422s a missing or malformed until', async () => {
    const { call } = await casesApp();
    expect((await call('GET', '/api/cases/due?until=holnap')).status).toBe(422);
    expect((await call('GET', '/api/cases/due')).status).toBe(422);
  });
});

describe('GET /api/cases', () => {
  it('orders by due date, undated last, and filters by status', async () => {
    const { call, put } = await threeCases();
    await put('01JAB6Z9Q3M8K7T2V5W4X1Y0RW', { title: 'Dátum nélkül' });
    const all = await call('GET', '/api/cases');
    expect(all.body.map((c: any) => c.title)).toEqual(['Gázszámla', 'Kárigény', 'Adóbevallás', 'Dátum nélkül']);
    expect(all.body[0]).not.toHaveProperty('context');
    const waiting = await call('GET', '/api/cases?status=waiting');
    expect(waiting.body.map((c: any) => c.id)).toEqual([CLAIM]);
    expect((await call('GET', '/api/cases?status=aktiv')).status).toBe(422);
  });
});

describe('GET /api/cases/:id', () => {
  it('returns the case with closed and open occurrences and its trail', async () => {
    const { call, close } = await threeCases();
    await close(GAS, { due_at: '2026-09-10' });
    const res = await call('GET', `/api/cases/${GAS}`);
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ id: GAS, due_at: '2026-10-10', version: 2 });
    expect(res.body.occurrences.map((o: any) => o.due_at)).toEqual(['2026-09-10']);
    expect(res.body.open_occurrences[0]).toBe('2026-10-10');
    expect(res.body.events.map((e: any) => e.kind)).toEqual(['occurrence.closed', 'case.created']);
    expect((await call('GET', `/api/cases/${TAX.replace('T', 'X')}`)).status).toBe(404);
  });
});

describe('GET /api/cases/events', () => {
  it('pages the change feed by id cursor, oldest first', async () => {
    const { call, put } = await threeCases();
    await put(CLAIM, { status: 'done', version: 1 });
    const all = await call('GET', '/api/cases/events?after=0');
    expect(all.body.map((e: any) => e.kind)).toEqual(['case.created', 'case.created', 'case.created', 'case.updated']);
    expect(JSON.parse(all.body[3].body)).toEqual({ fields: ['status'] });
    const after = await call('GET', `/api/cases/events?after=${all.body[2].id}&limit=5`);
    expect(after.body.map((e: any) => e.case_id)).toEqual([CLAIM]);
    expect((await call('GET', '/api/cases/events?after=x')).status).toBe(422);
  });
});
