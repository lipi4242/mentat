// flotta-menedzser: lezárás csak ellenőrző nonce-szal; a zöld jelentés az átvett incidenst nem zárja;
// emberi átvétel minden automatikus tokent érvénytelenít (futó műveletnél előbb drain).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { min, smApp } from './flotta-sm-fixture';
import { green } from './flotta-fixture';
import { signIn } from './sign-in';

async function asAdmin(f: Awaited<ReturnType<typeof smApp>>) {
  f.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  f.env.BETTER_AUTH_URL = 'http://localhost:8787';
  f.env.OTP_DRY_RUN = '1';
  const cookie = (await signIn(f.app, f.env, 'owner@example.com'))!;
  return (path: string, t: number) => f.call('POST', `/api/flotta/v1/incidents/${f.id}${path}`, {}, '', min(t), { cookie });
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const claimed = async () => { const f = await smApp(); const c = (await f.claim(1)).body; return { f, c }; };
const verify = (f: Awaited<ReturnType<typeof smApp>>, t: number, c: any, nonce: string, green_ = true, boot = 'boot-1:pid-2:start-3') =>
  f.exec(t, '/verify/result', { fence: c.fence, claim: c.claim, nonce, boot_id: boot, green: green_, summary: 'próba' });

describe('verification nonce closes, nothing else does', () => {
  it('a green probe with the nonce and a boot id closes; all tokens die', async () => {
    const { f, c } = await claimed();
    await f.run(2, c, 'doctor-fix', 'op-v-fix-0001');
    const s = await f.exec(3, '/verify/start', { fence: c.fence, claim: c.claim });
    expect(f.inc()).toMatchObject({ state: 'ellenorzes', nonce_fence: c.fence });
    expect((await verify(f, 4, c, s.body.nonce, true, '')).status).toBe(400);   // boot-azonosító nélkül nem
    // a claim gazdájának zöldje önmagában nem bizonyíték: kell a nonce UTÁNI box-jelentés
    expect((await verify(f, 4, c, s.body.nonce)).body.code).toBe('unproven');
    await f.live(3.5);                                         // a jelentés még pirosnak mutatja
    expect((await verify(f, 4, c, s.body.nonce)).body.code).toBe('unproven');
    await f.live(4.5, [green('vilma')]);
    const r = await verify(f, 5, c, s.body.nonce);
    expect(r.body.state).toBe('megoldva');
    expect(f.inc()).toMatchObject({ status: 'resolved', claim_hash: null, nonce_hash: null, fence: c.fence + 1, verified_boot_id: 'boot-1:pid-2:start-3' });
    expect((await f.run(6, c, 'doctor', 'op-after-0001')).check.body.code).toBe('stale');
    expect(f.tasks()[0].status).toBe('open');                 // a vetület a következő körben zár
    await f.cron(min(7));
    expect(f.tasks()[0].status).toBe('done');
    expect(f.mails).toEqual([]);                              // csendben marad: megoldotta
  });

  it('a stale nonce (an earlier verification round) cannot close', async () => {
    const { f, c } = await claimed();
    const first = (await f.exec(2, '/verify/start', { fence: c.fence, claim: c.claim })).body.nonce;
    expect((await verify(f, 3, c, first, false)).body.state).toBe('javit');
    const second = (await f.exec(4, '/verify/start', { fence: c.fence, claim: c.claim })).body.nonce;
    await f.live(4.5, [green('vilma')]);
    const old = await verify(f, 5, c, first);
    expect([old.status, old.body.code]).toEqual([409, 'stale']);
    expect(f.inc().state).toBe('ellenorzes');
    expect((await verify(f, 5, c, second)).body.state).toBe('megoldva');
  });

  it('verification cannot start while an op is open or an uncertain step is not assessed', async () => {
    const { f, c } = await claimed();
    await f.exec(2, '/ops/op-open-0001/intent', { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:vilma' });
    expect((await f.exec(3, '/verify/start', { fence: c.fence, claim: c.claim })).body.code).toBe('open_ops');
    await f.exec(3, '/ops/op-open-0001/result', { fence: c.fence, claim: c.claim, outcome: 'uncertain' });
    expect((await f.exec(4, '/verify/start', { fence: c.fence, claim: c.claim })).body.code).toBe('must_assess');
  });

  it('a nonce issued before a handover cannot close after it', async () => {
    const { f, c } = await claimed();
    const nonce = (await f.exec(2, '/verify/start', { fence: c.fence, claim: c.claim })).body.nonce;
    await f.cron(min(31));                                    // lejárt keret → átadás, új fence
    expect((await verify(f, 32, c, nonce)).body.code).toBe('stale');
    expect(f.inc().state).toBe('atadva');
  });

  it('a green box report does NOT close a claimed incident (only the nonce does)', async () => {
    const { f } = await claimed();
    await f.live(5, [green('vilma')]);
    expect(f.inc()).toMatchObject({ state: 'atveve', status: 'open' });
  });
});

describe('human takeover', () => {
  it('invalidates every automatic token at once when nothing runs, and sends no extra mail', async () => {
    const { f, c } = await claimed();
    const h = await f.call('POST', `/api/flotta/v1/incidents/${f.id}/human-claim`, {}, 'plain-gondnok-agent', min(2));
    expect(h.status).toBe(401);                               // csak admin-session, gépi token nem
    const adm = await asAdmin(f);
    const ok = await adm('/human-claim', 2);
    expect(ok.body).toMatchObject({ state: 'ember-kell', draining: false });
    expect(f.inc()).toMatchObject({ claim_hash: null, fence: c.fence + 1, human_by: 'owner@example.com' });
    expect((await f.run(3, c, 'doctor', 'op-hum-0001')).check.body.code).toBe('stale');
    await f.cron(min(4));
    expect(f.mails).toEqual([]);
    expect((await adm('/human-resolve', 5)).body.state).toBe('megoldva');
  });

  it('with a running op it drains first: no new step, then ember-kell once the op ends', async () => {
    const { f, c } = await claimed();
    const adm = await asAdmin(f);
    await f.exec(2, '/ops/op-hum-run01/intent', { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:vilma' });
    const h = await adm('/human-claim', 3);
    expect([h.status, h.body.draining]).toEqual([202, true]);
    expect((await f.exec(4, '/ops/check', { fence: c.fence, claim: c.claim, step: 'doctor', target: 'agent:vilma', op_id: 'op-hum-new01' })).body.code).toBe('draining');
    expect((await adm('/human-resolve', 4)).body.code).toBe('state');
    const r = await f.exec(5, '/ops/op-hum-run01/result', { fence: c.fence, claim: c.claim, outcome: 'ok' });
    expect(r.body.state).toBe('ember-kell');
    expect(f.inc()).toMatchObject({ drain: null, claim_hash: null, fence: c.fence + 1 });
  });
});
