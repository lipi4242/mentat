// flotta-menedzser: átvétel és átadás. Fix 30 perces keret (meghosszabbítás nincs), monoton fence;
// átadás a három okból (nincs claim 10 percen belül, lejárt keret, alkalmatlan lett a
// menedzser), és a lánc végén ember-kell + e-mail. A feladat a kiosztást követi (vetület).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GONDNOK, HELYETTES, min, smApp } from './flotta-sm-fixture';
import { green, red } from './flotta-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('claim', () => {
  it('only the assignee claims; it gets a 30-minute window, a higher fence and a secret; no renewal', async () => {
    const f = await smApp();
    expect(f.inc()).toMatchObject({ state: 'kiosztva', assigned_principal_id: 'p-gondnok', fence: 0 });
    expect((await f.claim(1, HELYETTES)).body.code).toBe('not_assignee');
    expect((await f.claim(1, 'plain-box-gondnok')).status).toBe(403);       // a box-token nem principal
    const c = await f.claim(2);
    expect(c.status).toBe(200);
    expect(c.body).toMatchObject({ fence: 1, state: 'atveve', target: 'agent:vilma', attempt_until: min(32).toISOString() });
    expect(typeof c.body.claim).toBe('string');
    expect(f.inc().claim_hash).not.toBe(c.body.claim);                        // csak a hash tárolódik
    const again = await f.claim(3);
    expect([again.status, again.body.code]).toEqual([409, 'state']);          // nincs megújítás
    expect(f.events()).toEqual(['opened', 'assigned', 'task', 'claimed']);
  });

  it('an unfit assignee cannot claim', async () => {
    const f = await smApp();
    // a gondnok javító-képessége (todo) piros
    expect((await f.report('gondnok', [red('gondnok', 'todo'), green('helyettes'), red('vilma', 'kuldes')], min(1))).status).toBe(200);
    expect(f.inc()).toMatchObject({ state: 'atadva', assigned_principal_id: 'p-helyettes' });   // a report azonnal átadta
    expect((await f.claim(2)).body.code).toBe('not_assignee');
  });
});

describe('handover (each trigger), new fence each time', () => {
  it('no claim within 10 minutes → the deputy, the task follows', async () => {
    const f = await smApp();
    await f.cron(min(9));
    expect(f.inc().state).toBe('kiosztva');
    await f.cron(min(10));
    expect(f.inc()).toMatchObject({ state: 'atadva', assigned_principal_id: 'p-helyettes', fence: 1, handovers: 1 });
    expect(f.tasks().map(t => [t.owner_id, t.status])).toEqual([['p-gondnok', 'done'], ['p-helyettes', 'open']]);
  });

  it('an expired attempt window → handover; the old fence can no longer act', async () => {
    const f = await smApp();
    const c = (await f.claim(1)).body;
    await f.cron(min(30));
    expect(f.inc().state).toBe('atveve');
    await f.cron(min(31));
    expect(f.inc()).toMatchObject({ state: 'atadva', assigned_principal_id: 'p-helyettes', fence: 2, claim_hash: null });
    const late = await f.run(32, c, 'doctor', 'op-late-0001');
    expect([late.check.status, late.check.body.code]).toEqual([409, 'stale']);
  });

  it('the claimer becoming unfit → handover', async () => {
    const f = await smApp();
    await f.claim(1);
    await f.live(5, [red('vilma', 'kuldes')], { ok: false, detail: 'a javító állapot-könyvtár nem írható' });
    // a box javító-próbája piros: a box MINDEN menedzsere alkalmatlan → a lánc elfogy
    expect(f.inc()).toMatchObject({ state: 'ember-kell', handovers: 1 });
    await f.cron(min(6));
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: vilma: kuldes piros (gondnok)']);
    expect(f.mails[0].text).toMatch(/a lánc elfogyott \(a menedzser alkalmatlan lett\)/);
  });

  it('the manager giving up (release) hands over at once', async () => {
    const f = await smApp();
    const c = (await f.claim(1)).body;
    const r = await f.call('POST', `/api/flotta/v1/incidents/${f.id}/release`, { fence: c.fence }, GONDNOK, min(2));
    expect(r.body.state).toBe('atadva');
    expect(f.inc().assigned_principal_id).toBe('p-helyettes');
  });

  it('chain exhausted → ember-kell and an immediate mail; more than 2 handovers show in coverage', async () => {
    const f = await smApp();
    await f.cron(min(10));                                   // gondnok → helyettes
    await f.cron(min(20));                                   // helyettes → nincs több
    expect(f.inc()).toMatchObject({ state: 'ember-kell', handovers: 2, assigned_principal_id: null });
    expect(f.mails).toHaveLength(1);
    expect(f.tasks().every(t => t.status === 'done')).toBe(true);
    f.raw.prepare('UPDATE flotta_incident SET handovers = 3').run();
    const s = await f.live(21);
    expect(s.body.coverage.handovers).toEqual([{ incident: f.id, target: 'agent:vilma', handovers: 3 }]);
    expect(s.body.coverage.human_needed.map((h: any) => h.incident)).toEqual([f.id]);
  });

  it('stays quiet when it should: a claimed incident inside its window sends nothing and does not move', async () => {
    const f = await smApp();
    await f.claim(1);
    for (const t of [5, 15, 25, 30]) { await f.live(t); await f.cron(min(t)); }
    expect(f.inc().state).toBe('atveve');
    expect(f.mails).toEqual([]);
  });
});
