// 11-08: az elutasított box-jelentés nem frissíti a box „utolsó jelentését” (a dead-man
// így megszólal), és maga is látható jel: a válasz `rejected` + kód, sorozatnál box-incidens.
// Mellette: a nyitott-incidens keret boxonkénti része.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { jsonReq } from './helpers';
import { flottaApp, green, min, red, T0 } from './flotta-fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
type F = Awaited<ReturnType<typeof flottaApp>>;
const box = (f: F, name: string) => f.raw.prepare('SELECT * FROM flotta_box WHERE name = ?').get(name) as any;

describe('rejected reports (11-08)', () => {
  it('a rejected report (409 cross-box) does not refresh last_report_at, and says so in the answer', async () => {
    const f = await flottaApp();
    await f.report('beta', [green('vilma')]);
    const res = await f.report('gondnok', [green('vilma')], min(5));
    expect(res.status).toBe(409);
    expect(res.body).toMatchObject({ rejected: true, code: 'cross-box', consecutive: 1 });
    expect(box(f, 'gondnok')).toMatchObject({ last_report_at: null, last_attempt_at: min(5).toISOString(), rejected_count: 1, last_reject: 'cross-box' });
  });

  it('a box whose every report is rejected trips the dead-man and, after 3 in a row, its own incident', async () => {
    const f = await flottaApp();
    await f.report('beta', [green('vilma')]);
    for (const t of [1, 11, 21]) expect((await f.report('gondnok', [green('vilma')], min(t))).status).toBe(409);
    const rej = f.incidents().filter(i => i.check_key === 'elutasitott-jelentes');
    expect(rej.map(i => [i.subject, i.status])).toEqual([['box:gondnok', 'open']]);
    expect(rej[0].detail).toBe('3 egymás utáni elutasított jelentés; utolsó ok: cross-box');
    f.raw.prepare(`UPDATE flotta_fleet SET deadman_min = 30`).run();
    await f.report('beta', [green('vilma')], min(25));
    await f.cron(min(31));
    expect(f.incidents().filter(i => i.check_key === 'deadman').map(i => i.subject)).toEqual(['box:gondnok']);
    // flotta-menedzser (v1): a box saját menedzserei sem jelentenek elfogadottat → fedetlen → ember-kell,
    // feladat nincs (az ágensnek így a box szövege sem jut el), a levél azonnal megy
    expect(f.incidents().find(i => i.check_key === 'elutasitott-jelentes')!.state).toBe('ember-kell');
    expect(f.tasks()).toEqual([]);
    expect(f.mails.map(m => m.subject)).toContain('Flotta-hiba: a gondnok box jelentéseit a központ elutasítja');
  });

  it('the next accepted report resets the counter and resolves the rejection and dead-man incidents', async () => {
    const f = await flottaApp();
    for (const t of [0, 1, 2]) await f.report('gondnok', [{ agent: 'rossz név!', red: [] }], min(t));
    await f.cron(min(31));
    expect(f.incidents().filter(i => i.status === 'open').map(i => i.check_key).sort()).toEqual(['deadman', 'deadman', 'elutasitott-jelentes']);
    expect((await f.report('gondnok', [green('gondnok')], min(32))).status).toBe(200);
    expect(box(f, 'gondnok')).toMatchObject({ rejected_count: 0, last_reject: null, last_report_at: min(32).toISOString() });
    expect(f.incidents().filter(i => i.subject === 'box:gondnok').every(i => i.status === 'resolved')).toBe(true);
  });

  it('validation (400) and box-mismatch (403) rejections count too; the rate limit applies before validation', async () => {
    const f = await flottaApp();
    expect((await f.report('beta', [{ agent: 'x', red: [{ check: 'NEM JÓ', detail: '' }] }])).body).toMatchObject({ code: 'invalid', consecutive: 1 });
    expect((await f.report('beta', [green('x')], new Date(T0.getTime() + 20000))).status).toBe(429);   // nem számít elutasításnak
    const mismatch = await f.app.request('/api/flotta/v1/report', jsonReq('POST', { box: 'gondnok', agents: [] }, { 'X-Mentat-Token': 'plain-box-beta' }), f.env);
    expect(mismatch.status).toBe(403);
    expect(box(f, 'beta')).toMatchObject({ rejected_count: 2, last_reject: 'box-mismatch', last_report_at: null });
  });
});

describe('per-box share of the incident cap', () => {
  it('one box cannot exhaust the fleet cap: its excess goes to the summary, another box can still open incidents', async () => {
    const f = await flottaApp({ responsible: false });
    f.raw.prepare('UPDATE flotta_fleet SET max_open_per_box = 2, max_open_incidents = 50').run();
    await f.report('beta', Array.from({ length: 5 }, (_, i) => red(`a${i}`, 'git')));
    expect(f.incidents().filter(i => i.box_id === 'b2' && i.check_key === 'git')).toHaveLength(2);
    expect(f.incidents().filter(i => i.check_key === 'tulterheles')).toHaveLength(1);
    await f.report('gondnok', [red('gondnok', 'git'), red('masik', 'todo')]);
    expect(f.incidents().filter(i => i.box_id === 'b1').map(i => i.check_key).sort()).toEqual(['git', 'todo']);
  });
});
