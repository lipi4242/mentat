// flotta-menedzser: a végrehajtó kapuja. Token-kötés (box + claim + fence + cél), a szándék a
// végrehajtás előtt, bizonytalan kimenet után kötelező doctor-felmérés, újraindítási keret
// atomikusan op-azonosítóval, és átadás csak a futó művelet lezárulta (vagy lejárta) után.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { min, smApp } from './flotta-sm-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const claimed = async () => { const f = await smApp(); const c = (await f.claim(1)).body; return { f, c }; };

describe('executor auth binds principal + target + operation', () => {
  it('wrong claim 403, wrong target 409, another box 403, the box token of another box cannot act', async () => {
    const { f, c } = await claimed();
    const b = { fence: c.fence, step: 'doctor', target: 'agent:vilma', op_id: 'op-aaaa-0001' };
    expect((await f.exec(2, '/ops/check', { ...b, claim: 'nem-az' })).status).toBe(403);
    expect((await f.exec(2, '/ops/check', { ...b, claim: c.claim, target: 'agent:gondnok' })).body.code).toBe('target');
    expect((await f.exec(2, '/ops/check', { ...b, claim: c.claim, step: 'rm -rf' })).status).toBe(400);
    const other = await f.call('POST', `/api/flotta/v1/incidents/${f.id}/ops/check`, { ...b, claim: c.claim }, 'plain-box-beta', min(2));
    expect([other.status, other.body.code]).toEqual([403, 'reach']);
    expect((await f.call('POST', `/api/flotta/v1/incidents/${f.id}/ops/check`, { ...b, claim: c.claim }, 'plain-gondnok-agent', min(2))).status).toBe(403);
    expect((await f.exec(2, '/ops/check', { ...b, claim: c.claim })).body).toMatchObject({ ok: true, must_assess: false });
  });

  it('a full step records intent before the result; state → javit; attempts counted', async () => {
    const { f, c } = await claimed();
    const r = await f.run(3, c, 'doctor-fix', 'op-fix-00000001');
    expect(r.result!.status).toBe(200);
    expect(f.ops().map(o => [o.step, o.state, o.summary])).toEqual([['doctor-fix', 'ok', 'doctor-fix kész']]);
    expect(f.inc()).toMatchObject({ state: 'javit', attempts: 1 });
    expect(f.events().filter(e => e.startsWith('op_'))).toEqual(['op_intent', 'op_result']);
  });

  it('an intent replay with the same op id is idempotent; a reused op id for another step is not', async () => {
    const { f, c } = await claimed();
    const b = { fence: c.fence, claim: c.claim, step: 'doctor', target: 'agent:vilma' };
    expect((await f.exec(2, '/ops/op-rep-0001/intent', b)).status).toBe(200);
    expect((await f.exec(2, '/ops/op-rep-0001/intent', b)).body.replay).toBe(true);
    await f.exec(2, '/ops/op-rep-0001/result', { fence: c.fence, claim: c.claim, outcome: 'ok', assessment: 'decided' });
    expect((await f.exec(3, '/ops/op-rep-0001/intent', b)).body.code).toBe('op_closed');
    // Codex-review: a visszajátszás csak ugyanarra a lépésre/célra/generációra idempotens
    expect((await f.exec(3, '/ops/op-rep-0002/intent', b)).status).toBe(200);
    expect((await f.exec(3, '/ops/op-rep-0002/intent', { ...b, step: 'doctor-fix' })).body.code).toBe('op_closed');
  });
});

describe('uncertain outcome → mandatory read-only doctor', () => {
  it('a crashed step (intent without result) makes the next non-doctor step 409; doctor "decided" clears it', async () => {
    const { f, c } = await claimed();
    const b = { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:vilma' };
    await f.exec(2, '/ops/op-crash-0001/intent', b);           // a végrehajtó itt „összeomlik”
    expect((await f.exec(3, '/ops/op-next-0001/intent', b)).body.code).toBe('must_assess');
    expect(f.ops()[0].state).toBe('uncertain');
    expect((await f.exec(3, '/ops/check', { ...b, op_id: 'op-next-0001' })).body.code).toBe('must_assess');
    expect((await f.run(4, c, 'doctor', 'op-doc-0001', 'ok', { assessment: 'decided' })).result!.status).toBe(200);
    expect(f.ops().map(o => o.state)).toEqual(['assessed', 'ok']);
    expect((await f.run(5, c, 'doctor-fix', 'op-fix-0002')).result!.status).toBe(200);
  });

  it('undecidable effect → ember-kell, all automatic tokens dead', async () => {
    const { f, c } = await claimed();
    await f.exec(2, '/ops/op-crash-0002/intent', { fence: c.fence, claim: c.claim, step: 'bridge-install', target: 'agent:vilma' });
    const r = await f.run(3, c, 'doctor', 'op-doc-0002', 'ok', { assessment: 'undecidable' });
    expect(r.result!.body.state).toBe('ember-kell');
    expect(f.inc()).toMatchObject({ claim_hash: null, fence: c.fence + 1 });
    expect((await f.run(4, c, 'doctor', 'op-doc-0003')).check.body.code).toBe('stale');
  });

  it('an unquarantine the executor refused (cause not machine-verifiable) → ember-kell', async () => {
    const { f, c } = await claimed();
    const r = await f.run(2, c, 'unquarantine', 'op-unq-00001', 'refused', { summary: 'cause' });
    expect(r.result!.body.state).toBe('ember-kell');
    expect(f.inc().human_reason).toMatch(/nem gépileg ellenőrizhető/);
  });
});

describe('fencing and drain', () => {
  it('handover waits for a running op; no new op meanwhile; then the late result is rejected as stale', async () => {
    const { f, c } = await claimed();
    const b = { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:vilma' };
    await f.exec(25, '/ops/op-long-0001/intent', b);           // határidő: 25 + 15 perc
    await f.cron(min(31));                                     // a keret lejárt, de fut egy művelet
    expect(f.inc()).toMatchObject({ state: 'javit', drain: 'handover', fence: c.fence });
    expect((await f.exec(31, '/ops/op-new-00001/intent', { ...b, step: 'doctor' })).body.code).toBe('draining');
    await f.cron(min(36));
    expect(f.inc().state).toBe('javit');                       // még mindig fut
    await f.cron(min(41));                                     // a lépés időkorlátja lejárt → bizonytalan, átadás
    expect(f.inc()).toMatchObject({ state: 'atadva', assigned_principal_id: 'p-helyettes', fence: c.fence + 1 });
    expect(f.ops()[0].state).toBe('uncertain');
    const late = await f.exec(42, '/ops/op-long-0001/result', { fence: c.fence, claim: c.claim, outcome: 'ok' });
    expect([late.status, late.body.code]).toEqual([409, 'stale']);
    expect(f.events()).toContain('stale_result');
    expect(f.ops()[0].state).toBe('uncertain');                // a késett eredmény nem hat
    // az új menedzser első lépése csak a felmérés lehet
    const c2 = (await f.claim(43, 'plain-helyettes-agent')).body;
    expect((await f.run(44, c2, 'doctor-fix', 'op-h-fix-0001')).check.body.code).toBe('must_assess');
  });

  it('a result that finishes inside the drain completes the handover immediately', async () => {
    const { f, c } = await claimed();
    await f.exec(25, '/ops/op-drain-001/intent', { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:vilma' });
    await f.cron(min(31));
    expect(f.inc().drain).toBe('handover');
    const r = await f.exec(32, '/ops/op-drain-001/result', { fence: c.fence, claim: c.claim, outcome: 'ok' });
    expect(r.body.state).toBe('atadva');
  });
});

describe('restart budget (3/hour/agent, reserved atomically by op id)', () => {
  it('the 4th restart-causing step in an hour → 409 budget and ember-kell, not the next manager', async () => {
    const { f, c } = await claimed();
    for (const [i, s] of (['doctor-fix', 'bridge-install', 'unquarantine'] as const).entries()) {
      expect((await f.run(2 + i, c, s, `op-bud-000${i}`)).result!.status).toBe(200);
    }
    expect((await f.run(5, c, 'doctor', 'op-bud-doc1')).result!.status).toBe(200);   // a doctor nem fogyaszt
    const fourth = await f.run(6, c, 'doctor-fix', 'op-bud-0004');
    expect([fourth.intent!.status, fourth.intent!.body.code]).toEqual([409, 'budget']);
    expect(f.inc()).toMatchObject({ state: 'ember-kell', claim_hash: null });
    expect(f.raw.prepare('SELECT count(*) AS n FROM flotta_restart_budget').get()).toEqual({ n: 3 });
  });

  it('concurrent reservations never exceed the budget', async () => {
    const { f, c } = await claimed();
    f.raw.prepare(`INSERT INTO flotta_restart_budget (op_id, fleet_id, agent, reserved_at) VALUES ('x1','default','vilma',?), ('x2','default','vilma',?)`)
      .run(min(1).toISOString(), min(1).toISOString());
    const b = (s: string) => ({ fence: c.fence, claim: c.claim, step: s, target: 'agent:vilma' });
    const rs = await Promise.all([f.exec(2, '/ops/op-race-0001/intent', b('doctor-fix')), f.exec(2, '/ops/op-race-0002/intent', b('bridge-install'))]);
    expect(rs.filter(r => r.status === 200)).toHaveLength(1);
    expect((f.raw.prepare(`SELECT count(*) AS n FROM flotta_restart_budget WHERE agent = 'vilma'`).get() as any).n).toBe(3);
  });

  it('the budget window slides: reservations older than an hour do not count', async () => {
    const { f, c } = await claimed();
    for (const i of [1, 2, 3]) f.raw.prepare(`INSERT INTO flotta_restart_budget VALUES (?, 'default', 'vilma', ?)`).run(`old${i}`, min(-61).toISOString());
    expect((await f.run(2, c, 'doctor-fix', 'op-slide-0001')).result!.status).toBe(200);
  });
});

