// A #53 review-javításai, mindegyikhez egy teszt: box-határ, kivezetés, fázis-izoláció,
// feladat-zárás ellenőrzése, levél utáni eseményhiba, dead-man verseny, feladat-idempotencia.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { deadman } from '../src/plugins/flotta/cron';
import { syncTasks } from '../src/plugins/flotta/todo-mirror';
import { jsonReq } from './helpers';
import { signIn } from './sign-in';
import { flottaApp, green, min, red, T0 } from './flotta-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const quiet = () => vi.spyOn(console, 'error').mockImplementation(() => {});
const fleetRow = (f: any) => f.raw.prepare(`SELECT * FROM flotta_fleet WHERE id = 'default'`).get();

describe('box boundary', () => {
  it('a box cannot close or open another box\'s agent incidents', async () => {
    const f = await flottaApp();
    await f.report('beta', [red('vilma', 'kuldes')]);
    expect((await f.report('gondnok', [green('vilma')], min(10))).status).toBe(409);       // zárni nem tud
    expect((await f.report('gondnok', [red('vilma', 'git')], min(11))).status).toBe(409);  // pirosítani sem
    expect(f.incidents().map(i => [i.check_key, i.status, i.box_id])).toEqual([['kuldes', 'open', 'b2']]);
    expect(f.raw.prepare(`SELECT box_id FROM flotta_agent WHERE name = 'vilma'`).get()).toEqual({ box_id: 'b2' });
  });

  it('moving an agent is an explicit admin action (release), then the new box may report it', async () => {
    const f = await flottaApp();
    f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
    f.env.BETTER_AUTH_URL = 'http://localhost:8787'; f.env.OTP_DRY_RUN = '1';
    const cookie = (await signIn(f.app, f.env, 'owner@example.com'))!;
    await f.report('beta', [red('vilma', 'kuldes')]);
    expect((await f.app.request('/api/flotta/v1/agents/vilma/release', jsonReq('POST', {}, { 'X-Mentat-Token': 'plain-box-gondnok' }), f.env)).status).toBe(401);
    expect((await f.app.request('/api/flotta/v1/agents/vilma/release', jsonReq('POST', {}, { cookie }), f.env)).status).toBe(200);
    expect(f.incidents()[0].status).toBe('resolved');
    expect((await f.report('gondnok', [green('vilma')], min(10))).status).toBe(200);
  });
});

describe('disable and drop-out', () => {
  it('disabling a box resolves its agent incidents too and stops repeat mails', async () => {
    const f = await flottaApp();
    f.raw.prepare('UPDATE flotta_fleet SET deadman_min = 100000').run();
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.cron(min(61));
    expect(f.mails).toHaveLength(1);
    f.raw.prepare(`UPDATE flotta_box SET disabled_at = ? WHERE name = 'beta'`).run(min(62).toISOString());
    await f.cron(min(61 + 400));   // a nyitott incidens kivezetett boxon: nincs ismétlés
    expect(f.mails).toHaveLength(1);
    f.raw.prepare(`UPDATE flotta_box SET disabled_at = NULL WHERE name = 'beta'`).run();
    f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
    f.env.BETTER_AUTH_URL = 'http://localhost:8787'; f.env.OTP_DRY_RUN = '1';
    const cookie = (await signIn(f.app, f.env, 'owner@example.com'))!;
    expect((await f.app.request('/api/flotta/v1/boxes/beta/disable', jsonReq('POST', {}, { cookie }), f.env)).status).toBe(200);
    expect(f.incidents().every(i => i.status === 'resolved')).toBe(true);
  });
});

describe('cron isolation', () => {
  it('a failing task mirror does not stop the e-mail', async () => {
    const f = await flottaApp();
    quiet();
    f.raw.exec(`CREATE TRIGGER boom BEFORE INSERT ON todo_task BEGIN SELECT RAISE(ABORT, 'boom'); END;`);
    expect((await f.report('gondnok', [green('gondnok'), red('vilma', 'kuldes')])).status).toBe(200);   // a box kérése nem bukik
    await f.report('gondnok', [green('gondnok'), red('vilma', 'kuldes')], min(5));
    const out = await f.cron(min(6)) as any;
    expect(out.default.tasks).toMatchObject({ error: expect.stringContaining('boom') });
    await f.cron(min(11));                       // 10 perc claim nélkül → a lánc elfogy → ember-kell → levél
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: vilma: kuldes piros (gondnok)']);
  });
});

describe('task closing and mail events', () => {
  it('records task_closed only when the task is really done; retries otherwise', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok'), red('vilma', 'kuldes')]);
    f.raw.exec(`CREATE TRIGGER swallow BEFORE UPDATE ON todo_task WHEN NEW.status = 'done' BEGIN SELECT RAISE(IGNORE); END;`);
    await f.report('gondnok', [green('gondnok'), green('vilma')], min(5));
    expect(f.tasks()[0].status).toBe('open');
    expect(f.raw.prepare(`SELECT count(*) AS n FROM flotta_incident_event WHERE kind = 'task_closed'`).get()).toEqual({ n: 0 });
    f.raw.exec('DROP TRIGGER swallow');
    await syncTasks(f.env.DB, fleetRow(f), min(15));
    expect(f.tasks()[0].status).toBe('done');
    expect(f.raw.prepare(`SELECT count(*) AS n FROM flotta_incident_event WHERE kind = 'task_closed'`).get()).toEqual({ n: 1 });
  });

  it('a failing history write after a sent mail does not send it again', async () => {
    const f = await flottaApp();
    quiet();
    f.raw.exec(`CREATE TRIGGER noevent BEFORE INSERT ON flotta_incident_event WHEN NEW.kind = 'mail_first' BEGIN SELECT RAISE(ABORT, 'x'); END;`);
    await f.report('gondnok', [red('gondnok', 'git')]);
    await f.cron(min(1));
    await f.cron(min(6));
    expect(f.mails).toHaveLength(1);
    expect(f.incidents()[0].mail_count).toBe(1);
  });

  it('the task follows the assignee: a changed assignee gets its own task, the old one is closed (flotta-menedzser)', async () => {
    const f = await flottaApp();
    f.manager('p-helyettes', 'helyettes', '*', 2);
    await f.report('gondnok', [green('gondnok'), green('helyettes'), red('vilma', 'kuldes')]);
    const [first] = f.tasks();
    expect(first.owner_id).toBe('p-gondnok');
    f.raw.prepare(`UPDATE flotta_incident SET assigned_principal_id = 'p-helyettes'`).run();   // a gazda változott
    await syncTasks(f.env.DB, fleetRow(f), min(5));
    expect(f.tasks().map(t => [t.owner_id, t.status])).toEqual([['p-gondnok', 'done'], ['p-helyettes', 'open']]);
    expect(f.incidents()[0].todo_task_id).toBe(f.tasks()[1].id);
    await syncTasks(f.env.DB, fleetRow(f), min(6));                  // idempotens: nincs harmadik
    expect(f.tasks()).toHaveLength(2);
  });
});

describe('dead-man race', () => {
  it('does not open a box incident if the box reported after the snapshot was read', async () => {
    const f = await flottaApp();
    const stale = f.raw.prepare(`SELECT * FROM flotta_box WHERE fleet_id = 'default'`).all();   // a régi pillanatkép
    await f.report('beta', [green('szervezo')], min(31));
    await f.report('gondnok', [green('gondnok')], min(31));
    const db = new Proxy(f.env.DB, { get: (t: any, k) => k !== 'prepare' ? t[k] : (sql: string) =>
      sql.startsWith('SELECT * FROM flotta_box WHERE fleet_id') ? { bind: () => ({ all: async () => ({ results: stale }) }) } : t.prepare(sql) });
    expect(await deadman(db as any, fleetRow(f), min(31))).toEqual([]);
    expect(f.incidents()).toEqual([]);
    expect(T0.getTime()).toBeLessThan(min(31).getTime());
  });
});
