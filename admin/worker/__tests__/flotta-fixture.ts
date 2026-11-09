// A flotta-ellenőrzés tesztjeinek közös terepe: valódi migrációk, egy box-token
// (csak flotta:report), egy felelős ágens (todo:write token + principal), és egy
// elkapott Resend-hívás. Valódi e-mail és valódi hálózat nincs: a fetch stub.
import { vi } from 'vitest';
import app from '../src/index';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { hashToken } from '../src/lib/tokens';
import { runCron } from '../src/plugins/flotta/cron';

export const T0 = new Date('2026-11-07T10:00:00.000Z');
export const min = (n: number, from = T0) => new Date(from.getTime() + n * 60000);

export async function flottaApp({ responsible = true } = {}) {
  const { DB, raw } = makeDb();
  const token = async (id: string, scopes: string) =>
    raw.prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES (?,?,?,?, '2999-01-01T00:00:00Z')`).run(id, id, await hashToken(`plain-${id}`), scopes);
  await token('box-gondnok', 'flotta:report');
  await token('box-beta', 'flotta:report');
  await token('gondnok-agent', 'todo:write');
  raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES ('p-gondnok','agent','gondnok','Gondnok','gondnok-agent','fixture','gondnok')`).run();
  await token('helyettes-agent', 'todo:write');
  raw.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,agent_token_id,created_by,idem_key) VALUES ('p-helyettes','agent','helyettes','Helyettes','helyettes-agent','fixture','helyettes')`).run();
  const manager = (principal: string, agent: string, scope: string, rank: number) =>
    raw.prepare(`INSERT INTO flotta_manager (id,fleet_id,principal_id,agent,scope,rank,created_at) VALUES (?, 'default', ?, ?, ?, ?, ?)`)
      .run(`m-${agent}-${scope}`, principal, agent, scope, rank, T0.toISOString());
  raw.prepare(`INSERT INTO flotta_fleet (id,name,updated_at) VALUES ('default','Flotta',?)`).run(T0.toISOString());
  if (responsible) manager('p-gondnok', 'gondnok', '*', 1);
  for (const [id, name] of [['b1', 'gondnok'], ['b2', 'beta']]) {
    raw.prepare(`INSERT INTO flotta_box (id,fleet_id,name,token_id,created_at) VALUES (?, 'default', ?, ?, ?)`).run(id, name, `box-${name}`, T0.toISOString());
  }
  const env = makeEnv({ DB, RESEND_API_KEY: 're_test_key', OTP_SENDER: 'noreply@example.com', BETTER_AUTH_URL: 'https://admin.example.com' });
  const mails: Array<{ to: string[]; subject: string; text: string }> = [];
  let resendStatus = 200;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    if (!String(url).includes('api.resend.com')) throw new Error(`unexpected network call: ${url}`);
    if (resendStatus !== 200) return new Response('{}', { status: resendStatus });
    mails.push(JSON.parse(String(init.body)));
    return new Response('{"id":"m"}', { status: 200 });
  }));
  // Az ingest a jelenlegi órát használja: a jelentés idejére a Date-et álljuk át.
  // flotta-menedzser: a box javító-próbája alapból zöld (nélküle a box menedzserei alkalmatlanok)
  const report = async (box: string, agents: unknown[], at = T0, tokenPlain = `plain-box-${box}`, repair: unknown = { ok: true }) => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(at);
    try {
      const res = await app.request('/api/flotta/v1/report', jsonReq('POST', { box, fleet_version: '1.4.0', agents, repair }, { 'X-Mentat-Token': tokenPlain }), env);
      return { status: res.status, body: await res.json() as any };
    } finally {
      vi.useRealTimers();
    }
  };
  // flotta-menedzser: tetszőleges hívás egy adott időpontban (claim, végrehajtó, kiadó)
  const call = async (method: string, path: string, body: unknown, token: string, at = T0, extra: Record<string, string> = {}) => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(at);
    try {
      const res = await app.request(path, jsonReq(method, body, { ...(token ? { 'X-Mentat-Token': token } : {}), ...extra }), env);
      return { status: res.status, body: await res.json() as any };
    } finally {
      vi.useRealTimers();
    }
  };
  const cron = (now: Date) => runCron(env, now);
  const incidents = () => raw.prepare(`SELECT * FROM flotta_incident ORDER BY opened_at, id`).all() as any[];
  const tasks = () => raw.prepare(`SELECT * FROM todo_task ORDER BY created_at, id`).all() as any[];
  const failResend = (status: number) => { resendStatus = status; };
  return { app, env, raw, report, call, token, cron, incidents, tasks, mails, failResend, manager };
}

export const red = (agent: string, check: string, detail = `${check} hiba`) => ({ agent, red: [{ check, detail }], ok: [] });
export const green = (agent: string) => ({ agent, red: [], ok: ['küldés (dry-run)', 'git'] });
