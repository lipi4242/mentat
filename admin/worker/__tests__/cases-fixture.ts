// Shared setup for the cases plugin API tests: the real app, the real
// migrations, and an agent token with the scopes under test.
import app from '../src/index';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { hashToken } from '../src/lib/tokens';

export const GAS = '01JAB6Z9Q3M8K7T2V5W4X1Y0RS';
export const TAX = '01JAB6Z9Q3M8K7T2V5W4X1Y0RT';
export const CLAIM = '01JAB6Z9Q3M8K7T2V5W4X1Y0RV';

export const gasBill = {
  title: 'Gázszámla',
  next_action: 'Átutalás, ha megjön a számla',
  recurrence: 'monthly:10',
  anchor_at: '2026-10-10',
  description: 'A havi gázszámla, átutalással.',
  brain_ref: 'agy/cases/gazszamla.md',
};

export async function casesApp(scopes = 'cases:write') {
  const { DB, raw } = makeDb();
  raw
    .prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES ('tok1','agent',?,?,'2999-01-01T00:00:00Z')`)
    .run(await hashToken('plain'), scopes);
  const env = makeEnv({ DB });
  const h: Record<string, string> = { 'X-Mentat-Token': 'plain' };
  const call = async (method: string, path: string, body?: unknown, headers: Record<string, string> = h) => {
    const res = await app.request(path, body === undefined ? { method, headers } : jsonReq(method, body, headers), env);
    const text = await res.text();
    return { status: res.status, body: text ? JSON.parse(text) : null };
  };
  const put = (id: string, body: unknown, headers?: Record<string, string>) => call('PUT', `/api/cases/${id}`, body, headers);
  const close = (id: string, body: unknown, headers?: Record<string, string>) =>
    call('POST', `/api/cases/${id}/occurrences`, body, headers);
  const count = (table: string) => (raw.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;
  return { env, raw, h, call, put, close, count };
}
