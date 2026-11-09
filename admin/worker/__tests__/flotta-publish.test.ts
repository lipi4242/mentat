// flotta-menedzser: a menedzser-lista egyetlen kiadója (`fleet managers publish`, külön config-token);
// régebbi verzió elutasítva; a box jelentő tokenje nem írhat konfigot. Plusz az állapotgép
// átmenet-táblája és a verzió-CAS (két egyidejű átmenetből pontosan egy nyer).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flottaApp } from './flotta-fixture';
import { move, STATES, type State } from '../src/plugins/flotta/states';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const LIST = [{ handle: 'gondnok', scope: '*', rank: 1 }, { handle: 'helyettes', scope: 'box:gondnok', rank: 1 }];

async function pub() {
  const f = await flottaApp({ responsible: false });
  await f.token('publisher', 'flotta:config');
  await f.token('both', 'flotta:config flotta:report');
  await f.token('wide', 'flotta:config todo:read');
  const put = (body: unknown, token = 'plain-publisher') => f.call('PUT', '/api/flotta/v1/managers', body, token);
  const managers = () => f.raw.prepare('SELECT principal_id, agent, scope, rank FROM flotta_manager ORDER BY scope, rank').all();
  return { ...f, put, managers };
}

describe('managers publish', () => {
  it('only a flotta:config token publishes; the box report token and a mixed token cannot', async () => {
    const f = await pub();
    expect((await f.put({ version: 1, managers: LIST }, 'plain-box-gondnok')).status).toBe(403);
    expect((await f.put({ version: 1, managers: LIST }, 'plain-both')).status).toBe(403);
    expect((await f.put({ version: 1, managers: LIST }, 'plain-wide')).status).toBe(403);   // pontosan egy jogkör
    expect((await f.put({ version: 1, managers: LIST }, 'plain-gondnok-agent')).status).toBe(403);
    expect((await f.put({ version: 1, managers: LIST }, '')).status).toBe(401);
    expect(f.managers()).toEqual([]);
    const ok = await f.put({ version: 1, managers: LIST });
    expect(ok.body).toMatchObject({ version: 1, unchanged: false });
    expect(f.managers()).toEqual([
      { principal_id: 'p-gondnok', agent: 'gondnok', scope: '*', rank: 1 },
      { principal_id: 'p-helyettes', agent: 'helyettes', scope: 'box:gondnok', rank: 1 }]);
  });

  it('versions: an older one is rejected, the same content is a no-op, the same version with other content is rejected', async () => {
    const f = await pub();
    expect((await f.put({ version: 3, managers: LIST })).status).toBe(200);
    const older = await f.put({ version: 2, managers: [] });
    expect([older.status, older.body.code, older.body.current]).toEqual([409, 'stale', 3]);
    expect((await f.put({ version: 3, managers: [...LIST].reverse() })).body.unchanged).toBe(true);
    expect((await f.put({ version: 3, managers: [] })).status).toBe(409);
    expect((await f.put({ version: 4, managers: [] })).status).toBe(200);
    expect(f.managers()).toEqual([]);
  });

  it('validates scope, rank, duplicates and the principals', async () => {
    const f = await pub();
    for (const bad of [[{ handle: 'gondnok', scope: 'beta', rank: 1 }], [{ handle: 'gondnok', scope: '*', rank: 0 }],
      [{ handle: 'gondnok', scope: '*', rank: 1 }, { handle: 'gondnok', scope: '*', rank: 2 }]]) {
      expect((await f.put({ version: 1, managers: bad })).status).toBe(400);
    }
    expect((await f.put({ version: 1, managers: [{ handle: 'nobody', scope: '*', rank: 1 }] })).status).toBe(422);
    expect((await f.put({ version: 0, managers: [] })).status).toBe(400);
    expect(f.managers()).toEqual([]);
  });
});

describe('state machine', () => {
  const ALLOWED: Record<State, State[]> = {
    nyitott: ['kiosztva', 'ember-kell', 'megoldva'],
    kiosztva: ['atveve', 'atadva', 'nyitott', 'ember-kell', 'megoldva'],
    atadva: ['atveve', 'atadva', 'nyitott', 'ember-kell', 'megoldva'],
    atveve: ['atveve', 'javit', 'ellenorzes', 'atadva', 'ember-kell'],
    javit: ['javit', 'ellenorzes', 'atadva', 'ember-kell'],
    ellenorzes: ['ellenorzes', 'megoldva', 'javit', 'atadva', 'ember-kell'],
    'ember-kell': ['ember-kell', 'megoldva'],
    megoldva: [],
  };
  const seed = (f: Awaited<ReturnType<typeof flottaApp>>, state: State) => {
    f.raw.prepare(`DELETE FROM flotta_incident_event`).run();
    f.raw.prepare(`DELETE FROM flotta_incident`).run();
    f.raw.prepare(`INSERT INTO flotta_incident (id, fleet_id, box_id, subject, agent, check_key, opened_at, last_red_at, state, status)
      VALUES ('i', 'default', 'b1', 'agent:x', 'x', 'git', '2026-11-07T10:00:00Z', '2026-11-07T10:00:00Z', ?, ?)`).run(state, state === 'megoldva' ? 'resolved' : 'open');
    return f.raw.prepare(`SELECT * FROM flotta_incident WHERE id = 'i'`).get() as any;
  };

  it('every transition: allowed ones apply with version+1 and an event; the rest throw', async () => {
    const f = await flottaApp();
    for (const from of STATES) for (const to of STATES) {
      const inc = seed(f, from);
      if (ALLOWED[from].includes(to)) {
        expect(await move(f.env.DB, inc, to, new Date()), `${from}→${to}`).toBe(true);
        const after = f.raw.prepare(`SELECT state, status, version, fence FROM flotta_incident WHERE id = 'i'`).get() as any;
        expect(after).toMatchObject({ state: to, version: 1, status: to === 'megoldva' ? 'resolved' : 'open', fence: to === 'megoldva' ? 1 : 0 });
        expect(f.raw.prepare('SELECT count(*) AS n FROM flotta_incident_event').get()).toEqual({ n: 1 });
      } else {
        await expect(move(f.env.DB, inc, to, new Date()), `${from}→${to}`).rejects.toThrow(/illegal transition/);
      }
    }
  });

  it('CAS: of two transitions from the same version exactly one wins, and only the winner writes an event', async () => {
    const f = await flottaApp();
    const inc = seed(f, 'kiosztva');
    const [a, b] = await Promise.all([move(f.env.DB, inc, 'atveve', new Date()), move(f.env.DB, inc, 'atadva', new Date())]);
    expect([a, b].filter(Boolean)).toHaveLength(1);
    expect(f.raw.prepare('SELECT count(*) AS n FROM flotta_incident_event').get()).toEqual({ n: 1 });
    expect(await move(f.env.DB, inc, 'ember-kell', new Date())).toBe(false);   // elavult verzió
  });
});
