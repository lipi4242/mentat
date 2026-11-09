// flotta-menedzser: a menedzser-lánc. Elsőbbség agent > box > *, azon belül rang, döntetlennél a
// handle; egy principal egyszer; kimarad, aki nem éri el a célt (v1: saját box), aki maga a
// cél, és aki alkalmatlan (néma, piros javító-próba, javítást érintő piros ellenőrzés).
// Egy apró, nem javítást érintő hiba nem zár ki. Üres lánc → ember-kell.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flottaApp, green, min, red, T0 } from './flotta-fixture';
import { chain, type Facts, type Member } from '../src/plugins/flotta/managers';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const owners = (f: Awaited<ReturnType<typeof flottaApp>>) =>
  Object.fromEntries(f.incidents().map(i => [`${i.subject}/${i.check_key}`, [i.state, i.assigned_principal_id]]));

// tiszta lánc-tesztek: minden menedzser az 'alfa' boxon, friss jelentéssel, zöld próbával
const m = (handle: string, scope: string, rank: number, principal = `p-${handle}`): Member =>
  ({ id: `${handle}-${scope}`, fleet_id: 'default', principal_id: principal, agent: handle, scope, rank, created_at: '', handle });
const facts = (managers: Member[], over: Partial<Facts> = {}): Facts => ({
  managers, now: T0, red: new Map(),
  fleet: { id: 'default', deadman_min: 30 } as Facts['fleet'],
  agentBox: new Map([...managers.map(x => [x.agent, { box: 'alfa', last_seen_at: T0.toISOString() }] as const), ['cel', { box: 'alfa', last_seen_at: T0.toISOString() }]]),
  boxes: new Map([['alfa', { name: 'alfa', disabled_at: null, last_report_at: T0.toISOString(), repair_ok: 1 } as any]]),
  ...over,
});
const names = (c: ReturnType<typeof chain>) => c.chain.map(x => x.handle);

describe('chain ordering (pure)', () => {
  it('agent scope beats box beats *, then rank, ties by handle', () => {
    const f = facts([m('zeta', '*', 1), m('alfa1', '*', 1), m('boxos', 'box:alfa', 5), m('celzott', 'agent:cel', 9), m('beta1', '*', 2)]);
    expect(names(chain({ agent: 'cel', box: 'alfa' }, f))).toEqual(['celzott', 'boxos', 'alfa1', 'zeta', 'beta1']);
  });

  it('a principal appears once, at its best place', () => {
    const f = facts([m('vezeto', '*', 1), m('helyettes', '*', 2), m('vezeto', 'agent:cel', 3)]);
    expect(names(chain({ agent: 'cel', box: 'alfa' }, f))).toEqual(['vezeto', 'helyettes']);
  });

  it('reach: a manager on another box is excluded (v1: own box only); the target itself too', () => {
    const f = facts([m('tavoli', '*', 1), m('cel', '*', 2), m('helyi', '*', 3)]);
    f.agentBox.set('tavoli', { box: 'beta', last_seen_at: T0.toISOString() });
    const c = chain({ agent: 'cel', box: 'alfa' }, f);
    expect(names(c)).toEqual(['helyi']);
    expect(c.excluded.map(e => [e.handle, e.why.split(' ')[0]])).toEqual([['tavoli', 'nem'], ['cel', 'ő']]);
  });

  it('unfit: silent, red repair probe, unmeasured probe, repair-related red; a minor red does not exclude', () => {
    const base = [m('vezeto', '*', 1), m('helyettes', '*', 2)];
    const red = (agent: string, k: string) => new Map([[`agent:${agent}`, new Set([k])]]);
    expect(names(chain({ agent: 'cel', box: 'alfa' }, facts(base, { red: red('vezeto', 'kuldes') })))).toEqual(['vezeto', 'helyettes']);
    expect(names(chain({ agent: 'cel', box: 'alfa' }, facts(base, { red: red('vezeto', 'todo') })))).toEqual(['helyettes']);
    const silent = facts(base); silent.agentBox.set('vezeto', { box: 'alfa', last_seen_at: min(-31).toISOString() });
    expect(names(chain({ agent: 'cel', box: 'alfa' }, silent))).toEqual(['helyettes']);
    for (const repair_ok of [0, null]) {
      const f = facts(base); (f.boxes.get('alfa') as any).repair_ok = repair_ok;
      expect(chain({ agent: 'cel', box: 'alfa' }, f).chain).toEqual([]);
    }
  });
});

describe('chain in the worker (reports → assignment)', () => {
  it('the first fit manager on the target box gets it; a deputy covers the manager itself', async () => {
    const f = await flottaApp();                              // gondnok '*' rang 1
    f.manager('p-helyettes', 'helyettes', '*', 2);
    await f.report('gondnok', [red('gondnok', 'todo'), red('szervezo', 'git'), green('helyettes')]);
    expect(owners(f)).toEqual({ 'agent:gondnok/todo': ['kiosztva', 'p-helyettes'], 'agent:szervezo/git': ['kiosztva', 'p-helyettes'] });
    await f.cron(min(1));
    expect(f.mails).toEqual([]);                              // van ép helyettes: nincs levél
  });

  it('a target on a box with no reachable manager is uncovered → ember-kell and an immediate mail', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok')]);
    await f.report('beta', [red('vilma', 'kuldes')]);
    expect(owners(f)).toEqual({ 'agent:vilma/kuldes': ['ember-kell', null] });
    await f.cron(min(1));
    expect(f.mails).toHaveLength(1);
    expect(f.mails[0].text).toMatch(/fedetlen cél — gondnok: nem éri el a beta boxot/);
    expect(f.tasks()).toEqual([]);
  });

  it('a box incident makes its agents\' incidents wait (no assignment) until it resolves', async () => {
    const f = await flottaApp();
    f.raw.prepare('UPDATE flotta_fleet SET deadman_min = 8').run();   // a 10 perces claim-időzítő előtt
    await f.report('beta', [green('masik')]);
    await f.report('gondnok', [green('gondnok'), red('szervezo', 'git')]);
    expect(owners(f)['agent:szervezo/git']).toEqual(['kiosztva', 'p-gondnok']);
    await f.report('beta', [green('masik')], min(5));
    await f.cron(min(9));                                     // a gondnok box néma → box-incidens
    expect(owners(f)['box:gondnok/deadman'][0]).toBe('ember-kell');
    expect(owners(f)['agent:szervezo/git']).toEqual(['nyitott', null]);   // vár, nem adódik át
    await f.cron(min(30));                                    // várakozás közben nincs claim-időzítő
    expect(owners(f)['agent:szervezo/git']).toEqual(['nyitott', null]);
    await f.report('gondnok', [green('gondnok'), red('szervezo', 'git')], min(33));
    expect(owners(f)['agent:szervezo/git']).toEqual(['kiosztva', 'p-gondnok']);   // nem számít próbáltnak
    // Codex-review: az újra-kiosztás után a menedzsernek ÚJ, nyitott feladata van (a régi zárult)
    expect(f.tasks().map(t => [t.owner_id, t.status])).toEqual([['p-gondnok', 'done'], ['p-gondnok', 'open']]);
  });

  it('managers without a measured repair probe are unfit (not measured is not green)', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok'), red('szervezo', 'git')], T0, undefined, null);
    expect(owners(f)['agent:szervezo/git'][0]).toBe('ember-kell');
  });
});
