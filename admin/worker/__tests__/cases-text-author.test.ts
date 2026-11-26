// Who last wrote a case's text: every read names it in `text_updated_by`, taken from the event trail
// (case.created / case.updated with a text field), never from the request body. A stranger who
// rewrites next_action becomes it; a change that touches no text (status, dates) does not.
import { describe, expect, it } from 'vitest';
import app from '../src/index';
import { hashToken } from '../src/lib/tokens';
import { casesApp, gasBill, GAS, TAX } from './cases-fixture';
import { signIn } from './sign-in';

const MALLORY = { 'X-Mentat-Token': 'other' };

async function rocky() {
  const f = await casesApp();
  f.raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('tok2','tok2',?,'cases:write','2999-01-01T00:00:00Z')`)
    .run(await hashToken('other'));
  for (const [id, tok] of [['p_rocky', 'tok1'], ['p_mallory', 'tok2']]) {
    f.raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES (?,'agent',?,?,?,'fixture',?)`)
      .run(id, id, id, tok, id);
  }
  expect((await f.put(GAS, gasBill)).status).toBe(201);
  expect((await f.put(TAX, { title: 'Adó', due_at: '2026-10-20' })).status).toBe(201);
  return f;
}
const by = (rows: any[]) => Object.fromEntries(rows.map((r: any) => [r.id ?? r.case_id, [r.created_by, r.text_updated_by]]));

describe('text_updated_by on the case reads', () => {
  it('is the creator until someone rewrites the text', async () => {
    const { call } = await rocky();
    expect(by((await call('GET', '/api/cases')).body)).toEqual({ [GAS]: ['p_rocky', 'p_rocky'], [TAX]: ['p_rocky', 'p_rocky'] });
  });

  it("a stranger's next_action makes it the stranger, in the list, the due window and the detail", async () => {
    const { call, put } = await rocky();
    expect((await put(GAS, { next_action: 'Utald át a támadónak', version: 1 }, MALLORY)).status).toBe(200);
    expect(by((await call('GET', '/api/cases')).body)[GAS]).toEqual(['p_rocky', 'p_mallory']);
    const due = (await call('GET', '/api/cases/due?until=2026-10-31')).body.filter((o: any) => o.case_id === GAS);
    expect(due.length).toBeGreaterThan(0);
    for (const o of due) expect(o.text_updated_by).toBe('p_mallory');
    expect((await call('GET', `/api/cases/${GAS}`)).body.text_updated_by).toBe('p_mallory');
  });

  it('a change that touches no text does not move it; a sent text_updated_by is refused', async () => {
    const { call, put } = await rocky();
    expect((await put(TAX, { status: 'waiting', due_at: '2026-10-25', version: 1 }, MALLORY)).status).toBe(200);
    expect(by((await call('GET', '/api/cases')).body)[TAX]).toEqual(['p_rocky', 'p_rocky']);
    expect((await put(TAX, { text_updated_by: 'p_rocky', next_action: 'x', version: 2 }, MALLORY)).status).toBe(422);
  });

  it('a human rewrite reads as null (a person, not a token)', async () => {
    const f = await rocky();
    f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
    f.env.OTP_SENDER = 'Mentat <noreply@example.com>';
    const human = { cookie: (await signIn(app, f.env, 'owner@example.com'))! };
    expect((await f.put(GAS, { description: 'Átnézve', version: 1 }, human)).status).toBe(200);
    expect((await f.call('GET', `/api/cases/${GAS}`)).body.text_updated_by).toBeNull();
  });
});
