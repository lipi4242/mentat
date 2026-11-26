// Who created a case: every read (list, due window, one case) names it in `created_by`, so an agent
// can tell its own and its owner's cases from a stranger's. An agent token reads as its todo
// principal, a token with no principal as `token:<id>`, a human session as null; a later write by
// someone else does not change it.
import { describe, expect, it } from 'vitest';
import app from '../src/index';
import { hashToken } from '../src/lib/tokens';
import { casesApp, gasBill, CLAIM, GAS, TAX } from './cases-fixture';
import { signIn } from './sign-in';

const HUMAN_CASE = '01JAB6Z9Q3M8K7T2V5W4X1Y0RX';

async function fourAuthors() {
  const f = await casesApp();
  for (const [id, plain] of [['tok2', 'other'], ['tok3', 'loose']]) {
    f.raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES (?,?,?,'cases:write','2999-01-01T00:00:00Z')`)
      .run(id, id, await hashToken(plain));
  }
  for (const [id, handle, tok] of [['p_rocky', 'rocky', 'tok1'], ['p_mallory', 'mallory', 'tok2']]) {
    f.raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES (?,'agent',?,?,?,'fixture',?)`)
      .run(id, handle, handle, tok, id);
  }
  f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  f.env.OTP_SENDER = 'Mentat <noreply@example.com>';
  const human = { cookie: (await signIn(app, f.env, 'owner@example.com'))! };
  expect((await f.put(GAS, gasBill)).status).toBe(201);
  expect((await f.put(TAX, { title: 'Adó', due_at: '2026-10-20' }, { 'X-Mentat-Token': 'other' })).status).toBe(201);
  expect((await f.put(CLAIM, { title: 'Kár', due_at: '2026-10-21' }, { 'X-Mentat-Token': 'loose' })).status).toBe(201);
  expect((await f.put(HUMAN_CASE, { title: 'Saját', due_at: '2026-10-22' }, human)).status).toBe(201);
  return f;
}

const EXPECTED: Record<string, string | null> = { [GAS]: 'p_rocky', [TAX]: 'p_mallory', [CLAIM]: 'token:tok3', [HUMAN_CASE]: null };

describe('created_by on the case reads', () => {
  it('the list names the creator of every case', async () => {
    const { call } = await fourAuthors();
    const all = (await call('GET', '/api/cases')).body;
    expect(Object.fromEntries(all.map((c: any) => [c.id, c.created_by]))).toEqual(EXPECTED);
  });

  it('every occurrence in the due window carries it', async () => {
    const { call } = await fourAuthors();
    const due = (await call('GET', '/api/cases/due?until=2026-10-31')).body;
    expect(new Set(due.map((o: any) => o.case_id)).size).toBe(4);
    for (const o of due) expect(o.created_by, `${o.case_id} ${o.due_at}`).toBe(EXPECTED[o.case_id]);
  });

  it('one case in full carries it, and a later write by someone else does not change it', async () => {
    const { call, put } = await fourAuthors();
    expect((await call('GET', `/api/cases/${TAX}`)).body.created_by).toBe('p_mallory');
    expect((await put(GAS, { next_action: 'Más', version: 1 }, { 'X-Mentat-Token': 'other' })).status).toBe(200);
    expect((await call('GET', `/api/cases/${GAS}`)).body.created_by).toBe('p_rocky');
  });
});
