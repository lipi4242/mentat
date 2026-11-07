// PUT /api/cases/:id — idempotent create/update keyed by an agent-generated
// ULID, guarded by `version` (optimistic lock).
import { describe, it, expect } from 'vitest';
import { casesApp, gasBill, GAS, TAX } from './cases-fixture';

describe('PUT /api/cases/:id — create and retry', () => {
  it('creates on the first PUT and is a no-op on a retried one (lost response)', async () => {
    const { put, count } = await casesApp();
    const first = await put(TAX, { title: 'Adóbevallás', due_at: '2027-05-20' });
    expect(first.status).toBe(201);
    expect(first.body).toMatchObject({ id: TAX, status: 'open', version: 1, due_at: '2027-05-20', extra: {} });
    const again = await put(TAX, { title: 'Adóbevallás', due_at: '2027-05-20' });
    expect(again.status).toBe(200);
    expect(again.body).toMatchObject({ id: TAX, version: 1, unchanged: true });
    expect(count('cases_case')).toBe(1);
    expect(count('cases_event')).toBe(1);
  });

  it('computes due_at of a recurring case from its anchor', async () => {
    const { put } = await casesApp();
    expect((await put(GAS, gasBill)).body).toMatchObject({ due_at: '2026-10-10', recurrence: 'monthly:10' });
  });

  it('takes the closed history in one migration PUT, and rolls due_at past it', async () => {
    const { put, count } = await casesApp();
    const occurrences = [{ due_at: '2026-10-10', status: 'done', done_at: '2026-10-08', note: 'átutalva' }];
    const res = await put(GAS, { ...gasBill, due_at: '2026-11-10', occurrences });
    expect(res.status).toBe(201);
    expect(res.body.due_at).toBe('2026-11-10');
    expect(res.body.occurrences).toEqual([expect.objectContaining(occurrences[0])]);
    // the retry of that same migration step writes nothing new
    expect((await put(GAS, { ...gasBill, due_at: '2026-11-10', occurrences })).status).toBe(200);
    expect(count('cases_occurrence')).toBe(1);
  });

  it('mirrors the brain context and hashes it', async () => {
    const { put } = await casesApp();
    const res = await put(TAX, { title: 'Adó', context: '# Adó\n' });
    expect(res.body.context).toBe('# Adó\n');
    expect(res.body.context_hash).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe('PUT /api/cases/:id — version lock', () => {
  it('updates with the version it read, and bumps it', async () => {
    const { put } = await casesApp();
    await put(TAX, { title: 'Adó' });
    const res = await put(TAX, { status: 'waiting', next_action: 'Várunk a NAV-ra', version: 1 });
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ status: 'waiting', next_action: 'Várunk a NAV-ra', title: 'Adó', version: 2 });
  });

  it('accepts the version as If-Match too', async () => {
    const { put, h } = await casesApp();
    await put(TAX, { title: 'Adó' });
    expect((await put(TAX, { title: 'Adó 2027' }, { ...h, 'If-Match': '1' })).status).toBe(200);
  });

  it('409s a stale or missing version and names the current one', async () => {
    const { put } = await casesApp();
    await put(TAX, { title: 'Adó' });
    await put(TAX, { title: 'Adó 2027', version: 1 });
    const stale = await put(TAX, { title: 'Adó!', version: 1 });
    expect(stale.status).toBe(409);
    expect(stale.body).toMatchObject({ version: 2 });
    expect((await put(TAX, { title: 'Adó!' })).status).toBe(409);
  });
});

describe('PUT /api/cases/:id — 422', () => {
  it.each([
    ['a non-ULID id', 'not-a-ulid', { title: 'x' }, /id/],
    ['an unknown field', TAX, { title: 'x', owner: 'me' }, /owner/],
    ['a field the base model dropped', TAX, { title: 'x', waiting_on: 'NAV' }, /waiting_on/],
    ['a non-text description', TAX, { title: 'x', description: 5 }, /description/],
    ['a bad status', TAX, { title: 'x', status: 'aktiv' }, /status/],
    ['no title on create', TAX, { status: 'open' }, /title/],
    ['a recurrence without anchor_at', TAX, { title: 'x', recurrence: 'monthly:10' }, /anchor_at/],
    ['an anchor off the series', TAX, { title: 'x', recurrence: 'monthly:10', anchor_at: '2026-10-11' }, /anchor_at/],
    ['a bad recurrence', TAX, { title: 'x', recurrence: 'monthly:32', anchor_at: '2026-10-10' }, /recurrence/],
    ['a bad date', TAX, { title: 'x', due_at: '2026-02-30' }, /due_at/],
    ['extra that is not an object', TAX, { title: 'x', extra: [1] }, /extra/],
    ['a case_id that is not the URL id', TAX, { title: 'x', case_id: GAS }, /case_id/],
    ['a stale due_at on a recurring case', GAS, { ...gasBill, due_at: '2026-11-10' }, /2026-10-10/],
    ['occurrences that skip a month', GAS, { ...gasBill, occurrences: [{ due_at: '2026-11-10', status: 'done' }] }, /occurrences/],
  ])('rejects %s', async (_label, id, body, msg) => {
    const { put, count } = await casesApp();
    const res = await put(id as string, body);
    expect(res.status).toBe(422);
    expect(JSON.stringify(res.body)).toMatch(msg as RegExp);
    expect(count('cases_case')).toBe(0);
  });

  it('refuses to rewrite closed occurrences through PUT', async () => {
    const { put } = await casesApp();
    await put(GAS, gasBill);
    const res = await put(GAS, { occurrences: [{ due_at: '2026-10-10', status: 'done' }], version: 1 });
    expect(res.status).toBe(422);
    expect(res.body.error).toMatch(/occurrences/);
  });
});

describe('scopes', () => {
  it('a cases:read token reads but cannot write (403); no token is 401', async () => {
    const { put, call } = await casesApp('cases:read');
    expect((await put(TAX, { title: 'x' })).status).toBe(403);
    expect((await call('GET', '/api/cases')).status).toBe(200);
    expect((await call('GET', '/api/cases', undefined, {})).status).toBe(401);
  });

  it('a token with neither scope is 403 on reads too', async () => {
    const { call } = await casesApp('widgets:write');
    expect((await call('GET', '/api/cases')).status).toBe(403);
    expect((await call('GET', '/api/cases/due?until=2027-01-01')).status).toBe(403);
  });
});

describe('PUT /api/cases/:id — the base model', () => {
  it('a one-off case: a deadline, a description, closed by status', async () => {
    const { put, call } = await casesApp();
    const res = await put(TAX, { title: 'Adóbevallás', description: 'Az éves SZJA-bevallás.', due_at: '2027-05-20' });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ description: 'Az éves SZJA-bevallás.', due_at: '2027-05-20', recurrence: null });
    expect(res.body).not.toHaveProperty('waiting_on');
    expect(res.body).not.toHaveProperty('category');
    const due = await call('GET', '/api/cases/due?until=2027-05-31');
    expect(due.body.map((o: any) => [o.case_id, o.due_at, o.closable])).toEqual([[TAX, '2027-05-20', true]]);
    expect((await put(TAX, { status: 'done', version: 1 })).body).toMatchObject({ status: 'done', version: 2 });
    expect((await call('GET', '/api/cases/due?until=2027-05-31')).body).toEqual([]);
  });
});
