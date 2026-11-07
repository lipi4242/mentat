import app from '../src/index';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { hashToken } from '../src/lib/tokens';
export async function todoApp(scopes = 'todo:write') {
  const { DB, raw } = makeDb();
  for (const id of ['a','b','c']) {
    raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES (?,?,?,?, '2999-01-01T00:00:00Z')`).run(id, id, await hashToken(id), scopes);
    raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES (?,'agent',?,?,?,'fixture',?)`).run(id, id, id.toUpperCase(), id, id);
  }
  const env = makeEnv({ DB });
  const call = async (method: string, path: string, body?: unknown, headers: Record<string, string> = { 'X-Mentat-Token': 'a' }) => {
    const res = await app.request(`/api/todo/v1${path}`, body === undefined ? { method, headers } : jsonReq(method, body, headers), env);
    return { status: res.status, body: await res.json() as any };
  };
  const create = async (set: Record<string, unknown> = {}) => (await call('POST', '/tasks', { title: 'Task', idem_key: crypto.randomUUID(), ...set })).body;
  const count = (table = 'todo_event') => (raw.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;
  return { call, create, count, raw, env };
}
