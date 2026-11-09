// CISO-audit (#53): korlátok (AD-09), a rendszer saját résztvevője (AD-10), box-token
// élettartam és visszavonás (AD-11), és az AD-08 box-határ változatai.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { runCron } from '../src/plugins/flotta/cron';
import { SYSTEM_PRINCIPAL } from '../src/plugins/flotta/system-principal';
import { jsonReq } from './helpers';
import { signIn } from './sign-in';
import { flottaApp, green, min, red, T0 } from './flotta-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
type F = Awaited<ReturnType<typeof flottaApp>>;
const set = (f: F, sql: string) => f.raw.prepare(`UPDATE flotta_fleet SET ${sql}`).run();
const many = (n: number, check = 'git') => Array.from({ length: n }, (_, i) => red(`a${i}`, check));
const overloadInc = (f: F) => f.incidents().filter(i => i.check_key === 'tulterheles');
async function session(f: F) {
  f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  f.env.BETTER_AUTH_URL = 'http://localhost:8787'; f.env.OTP_DRY_RUN = '1';
  const cookie = (await signIn(f.app, f.env, 'owner@example.com'))!;
  return (method: string, path: string, body: unknown = {}) => f.app.request(path, jsonReq(method, body, { cookie }), f.env);
}

describe('AD-09 report rate limit', () => {
  it('accepts at most one report per 60 s per box; the excess gets 429 and writes nothing', async () => {
    const f = await flottaApp();
    expect((await f.report('beta', [green('vilma')])).status).toBe(200);
    expect((await f.report('beta', [red('vilma', 'git')], new Date(T0.getTime() + 30000))).status).toBe(429);
    expect(f.incidents()).toEqual([]);
    expect((await f.report('gondnok', [green('gondnok')], new Date(T0.getTime() + 30000))).status).toBe(200);   // másik box: saját kerete
    expect((await f.report('beta', [red('vilma', 'git')], min(1))).status).toBe(200);
    expect(f.raw.prepare('SELECT count(*) AS n FROM flotta_report').get()).toEqual({ n: 3 });
  });
});

describe('AD-09 per-fleet caps', () => {
  it('open incidents: above the cap one summary incident instead of new ones, and one summary mail', async () => {
    const f = await flottaApp({ responsible: false });
    set(f, 'max_open_incidents = 3, deadman_min = 100000');
    await f.report('beta', many(6));
    expect(f.incidents().filter(i => i.check_key === 'git')).toHaveLength(3);
    expect(overloadInc(f)).toHaveLength(1);
    await f.report('beta', many(6), min(1));   // ismételt áradat: továbbra is egy összegző
    expect(overloadInc(f)).toHaveLength(1);
    await f.cron(min(2));
    expect(f.mails.filter(m => m.subject.includes('túl sok flotta-hiba'))).toHaveLength(1);
  });

  it('tasks per hour: above the cap the rest waits, flagged by the summary incident, then goes out an hour later', async () => {
    const f = await flottaApp();
    set(f, 'max_tasks_per_hour = 2, deadman_min = 100000');
    // flotta-menedzser: a menedzser a célok boxán ül (v1: csak saját box érhető el)
    await f.report('gondnok', [green('gondnok'), ...many(4)]);
    expect(f.tasks()).toHaveLength(2);
    expect(overloadInc(f)).toHaveLength(1);
    await f.cron(min(2));
    expect(f.tasks()).toHaveLength(2);
    // egy óra múlva a keret felszabadul (a 10 perces claim-időzítő miatt az időt nem léptetjük, hanem a naplót)
    f.raw.prepare(`UPDATE flotta_incident_event SET at = ? WHERE kind = 'task'`).run(min(-61).toISOString());
    await f.cron(min(3));
    expect(f.tasks()).toHaveLength(4);
  });

  it('mails per hour: at most the cap plus one summary mail; the rest is sent when the budget frees; the summary then resolves', async () => {
    const f = await flottaApp({ responsible: false });
    set(f, 'max_mails_per_hour = 2, deadman_min = 100000, debounce_reports = 1');
    await f.report('beta', many(4));
    await f.cron(min(1));
    expect(f.mails).toHaveLength(2);
    expect(overloadInc(f)).toHaveLength(1);
    await f.cron(min(6));
    expect(f.mails).toHaveLength(3);                  // + az összegző levél, és semmi más
    expect(f.mails[2].subject).toContain('túl sok flotta-hiba');
    await f.cron(min(62));
    expect(f.mails.filter(m => m.subject.startsWith('Flotta-hiba: a'))).toHaveLength(4);   // a visszatartottak is kimentek
    await f.report('beta', many(4).map(a => green(a.agent)), min(130));
    await f.cron(min(131));   // 4 „Megoldva” levél: a keret 2, a többi vár
    await f.cron(min(200));
    expect(f.mails.filter(m => m.subject.startsWith('Megoldva: a'))).toHaveLength(4);
    await f.cron(min(270));   // minden keret alatt: az összegző lezárul, és megy róla egy „Megoldva”
    await f.cron(min(275));
    expect(overloadInc(f)[0].status).toBe('resolved');
    expect(f.mails.at(-1)!.subject).toBe('Megoldva: túl sok flotta-hiba egyszerre (a többi összevonva)');
  });

  it('a box cannot itself open a deadman or summary incident', async () => {
    const f = await flottaApp();
    await f.report('beta', [{ agent: 'vilma', red: [{ check: 'deadman', detail: 'x' }, { check: 'tulterheles', detail: 'y' }] }]);
    expect(f.incidents().map(i => [i.subject, i.check_key])).toEqual([['agent:vilma', 'egyeb']]);
  });
});

describe('AD-09 per-fleet cron isolation', () => {
  async function twoFleets() {
    const f = await flottaApp();
    f.raw.prepare(`INSERT INTO flotta_fleet (id, name, updated_at) VALUES ('aaa', 'Másik', ?)`).run(T0.toISOString());
    f.raw.prepare(`INSERT INTO flotta_box (id, fleet_id, name, token_id, created_at) VALUES ('bx', 'aaa', 'x1', NULL, ?)`).run(T0.toISOString());
    await f.report('gondnok', [red('gondnok', 'git')]);   // a default flotta menedzserének saját hibája: azonnali levél
    return f;
  }

  it('an error in one fleet does not stop another', async () => {
    const f = await twoFleets();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    f.raw.exec(`CREATE TRIGGER aaa_boom BEFORE INSERT ON flotta_incident WHEN NEW.fleet_id = 'aaa' BEGIN SELECT RAISE(ABORT, 'aaa'); END;`);
    f.raw.prepare(`UPDATE flotta_fleet SET deadman_min = 100000 WHERE id = 'default'`).run();
    const out = await f.cron(min(40)) as any;
    expect(out.aaa.deadman).toMatchObject({ error: expect.stringContaining('aaa') });
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: gondnok: git piros (gondnok)']);
  });

  it('a slow fleet stops at its time budget; the next fleet still gets its turn', async () => {
    const f = await twoFleets();
    f.raw.prepare(`UPDATE flotta_fleet SET deadman_min = 100000 WHERE id = 'default'`).run();
    for (const n of ['x2', 'x3', 'x4']) f.raw.prepare(`INSERT INTO flotta_box (id, fleet_id, name, token_id, created_at) VALUES (?, 'aaa', ?, NULL, ?)`).run(n, n, T0.toISOString());
    const slow = globalThis.fetch;
    vi.stubGlobal('fetch', vi.fn(async (u: string, i: RequestInit) => { await new Promise(r => setTimeout(r, 80)); return slow(u, i); }));
    await runCron(f.env, min(40), 200);              // fél keret az e-mailre: 100 ms
    const aaa = f.mails.filter(m => /a x\d box/.test(m.subject)), mine = f.mails.filter(m => m.subject.includes('gondnok: git'));
    expect(aaa.length).toBeLessThan(4);
    expect(mine).toHaveLength(1);
  });
});

describe('AD-10 system principal', () => {
  it('tasks are created, commented and closed by the system principal; the manager owns them', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok'), red('vilma', 'kuldes')]);
    await f.report('gondnok', [green('gondnok'), green('vilma')], min(5));
    const [t] = f.tasks();
    expect(t).toMatchObject({ owner_id: 'p-gondnok', created_by: SYSTEM_PRINCIPAL, done_by: SYSTEM_PRINCIPAL, status: 'done' });
    const actors = f.raw.prepare('SELECT DISTINCT actor_id FROM todo_event WHERE task_id = ?').all(t.id).map((e: any) => e.actor_id);
    expect(actors).toEqual([SYSTEM_PRINCIPAL]);
    expect(f.raw.prepare('SELECT author_id FROM todo_comment WHERE task_id = ?').get(t.id)).toEqual({ author_id: SYSTEM_PRINCIPAL });
    const recipients = f.raw.prepare('SELECT recipients_json FROM todo_event WHERE task_id = ?').all(t.id).map((e: any) => e.recipients_json);
    expect(new Set(recipients)).toEqual(new Set(['["p-gondnok"]']));
    // a rendszer-résztvevővel nem lehet belépni
    expect(f.raw.prepare('SELECT active, scopes FROM agent_token WHERE id = ?').get(SYSTEM_PRINCIPAL)).toEqual({ active: 0, scopes: '' });
    expect((f.raw.prepare('SELECT disabled_at FROM todo_principal WHERE id = ?').get(SYSTEM_PRINCIPAL) as any).disabled_at).not.toBeNull();
  });
});

describe('AD-11 box token lifetime and revocation', () => {
  it('a new box token lives 90 days by default, at most 180; disabling the box revokes it', async () => {
    const f = await flottaApp();
    const call = await session(f);
    const made = await (await call('POST', '/api/flotta/v1/boxes', { name: 'gamma' })).json() as any;
    const days = (Date.parse(made.expires_at.replace(' ', 'T') + 'Z') - Date.now()) / 86400000;
    expect(Math.round(days)).toBe(90);
    expect((await call('POST', '/api/flotta/v1/boxes', { name: 'delta', days: 365 })).status).toBe(400);
    const rep = await f.app.request('/api/flotta/v1/report', jsonReq('POST', { box: 'gamma', agents: [] }, { 'X-Mentat-Token': made.token }), f.env);
    expect((await rep.json() as any).token_expires_at).toBe(made.expires_at);
    expect((await call('POST', '/api/flotta/v1/boxes/gamma/disable')).status).toBe(200);
    expect(f.raw.prepare('SELECT active FROM agent_token WHERE id = ?').get(made.token_id)).toEqual({ active: 0 });
    const after = await f.app.request('/api/flotta/v1/report', jsonReq('POST', { box: 'gamma', agents: [] }, { 'X-Mentat-Token': made.token }), f.env);
    expect(after.status).toBe(401);   // AD-08: a kivezetett box tokenje semmire nem jó
  });
});

describe('AD-08 cross-box variants', () => {
  it('same-name agent on two boxes: the second box is refused, also after the first goes silent', async () => {
    const f = await flottaApp();
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.cron(min(40));   // a beta box néma lett
    expect((await f.report('gondnok', [green('vilma')], min(41))).status).toBe(409);
    expect(f.incidents().find(i => i.subject === 'agent:vilma').status).toBe('open');
  });

  it('release then re-claim: only the box that reports first after the release gets the agent', async () => {
    const f = await flottaApp();
    const call = await session(f);
    await f.report('beta', [green('vilma')]);
    await call('POST', '/api/flotta/v1/agents/vilma/release');
    expect((await f.report('gondnok', [red('vilma', 'git')], min(1))).status).toBe(200);
    expect((await f.report('beta', [green('vilma')], min(2))).status).toBe(409);   // a régi box már nem zárhatja
    expect(f.incidents().find(i => i.subject === 'agent:vilma').status).toBe('open');
  });
});
