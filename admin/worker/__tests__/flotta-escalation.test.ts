// 11-07: az eszkaláció pirosra tud menni (levél megy), és csendben marad, amikor
// kell. Dead-man, időzítés, ismétlés, „megoldva”, idempotencia, a felelős nélküli
// út és a felelős ágenst érintő út.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flottaApp, green, min, red, T0 } from './flotta-fixture';

/** A dead-man ezekben a tesztekben ne szóljon közbe (a boxok itt nem jelentenek folyamatosan). */
const noDeadman = (f: Awaited<ReturnType<typeof flottaApp>>) => f.raw.prepare('UPDATE flotta_fleet SET deadman_min = 100000').run();

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('flotta escalation (cron)', () => {
  it('stays quiet while managers work on it, then mails the owner once after escalate_min', async () => {
    const f = await flottaApp();
    noDeadman(f);
    f.manager('p-helyettes', 'helyettes', '*', 2);
    const live = (t: number) => f.report('gondnok', [green('gondnok'), green('helyettes'), red('vilma', 'kuldes')], min(t));
    await live(0);
    const id = f.incidents()[0].id;
    expect((await f.call('POST', `/api/flotta/v1/incidents/${id}/claim`, {}, 'plain-gondnok-agent', min(2))).status).toBe(200);
    for (const t of [10, 20, 29]) { await live(t); await f.cron(min(t)); }
    await live(31); await f.cron(min(32));                  // a 30 perces keret lejárt → átadás a helyettesnek
    expect(f.incidents()[0]).toMatchObject({ state: 'atadva', assigned_principal_id: 'p-helyettes', handovers: 1 });
    expect((await f.call('POST', `/api/flotta/v1/incidents/${id}/claim`, {}, 'plain-helyettes-agent', min(35))).status).toBe(200);
    for (const t of [40, 50, 59]) { await live(t); await f.cron(min(t)); }
    expect(f.mails).toEqual([]);                            // csend: dolgoznak rajta
    await f.cron(min(61));
    expect(f.mails).toHaveLength(1);                        // pirosra megy
    expect(f.mails[0].to).toEqual(['owner@example.com']);
    expect(f.mails[0].subject).toBe('Flotta-hiba: vilma: kuldes piros (gondnok)');
    expect(f.mails[0].text).toContain('60 perc alatt nem oldódott meg');
    expect(f.mails[0].text).toMatch(/handover → helyettes/);  // ki mit próbált
    await f.cron(min(66));                                  // újrafutás: nincs második levél
    await f.cron(min(61));                                  // ugyanaz az időpont még egyszer (cron-retry)
    expect(f.mails).toHaveLength(1);
  });

  it('repeats every repeat_min while open, and sends one short "megoldva" on resolve', async () => {
    const f = await flottaApp();
    noDeadman(f);
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.cron(min(61));
    await f.cron(min(61 + 359));
    expect(f.mails).toHaveLength(1);
    await f.cron(min(61 + 360));
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: vilma: kuldes piros (beta)', 'Flotta-hiba: vilma: kuldes piros (beta)']);
    await f.report('beta', [green('vilma')], min(500));
    await f.cron(min(505));
    await f.cron(min(510));
    expect(f.mails.map(m => m.subject.split(':')[0])).toEqual(['Flotta-hiba', 'Flotta-hiba', 'Megoldva']);
  });

  it('a resolved incident that never mailed sends nothing', async () => {
    const f = await flottaApp();
    noDeadman(f);
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.report('beta', [green('vilma')], min(10));
    await f.cron(min(200));
    expect(f.mails).toEqual([]);
  });

  it('no responsible agent: mails after the debounce (2 consecutive red reports), not on the first', async () => {
    const f = await flottaApp({ responsible: false });
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.cron(min(1));
    expect(f.mails).toEqual([]);
    await f.report('beta', [red('vilma', 'kuldes')], min(10));
    await f.cron(min(11));
    expect(f.mails).toHaveLength(1);
    expect(f.mails[0].text).toContain('nincs illetékes felelős ágens');
  });

  it('a disabled responsible principal counts as none', async () => {
    const f = await flottaApp();
    f.raw.prepare(`UPDATE todo_principal SET disabled_at = '2026-11-01' WHERE id = 'p-gondnok'`).run();
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.report('beta', [red('vilma', 'kuldes')], min(10));
    await f.cron(min(11));
    expect(f.mails).toHaveLength(1);
  });

  it('an incident of the responsible agent itself mails immediately', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [red('gondnok', 'todo', 'mentat-todo me hibás')]);
    await f.cron(min(1));
    expect(f.mails).toHaveLength(1);
    expect(f.mails[0].text).toMatch(/emberi beavatkozás kell: fedetlen cél — gondnok: ő maga a cél/);
    expect(f.tasks()).toEqual([]);                    // ami le van állva, magát sem javítja
  });

  it('dead-man: the manager\'s own silent box mails at once (nobody else can fix it)', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok')]);
    await f.report('beta', [green('szervezo')], min(20));
    await f.cron(min(29));
    expect(f.incidents()).toEqual([]);
    await f.cron(min(31));
    expect(f.incidents().map(i => [i.subject, i.check_key])).toEqual([['box:gondnok', 'deadman']]);
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: a gondnok box nem jelentett']);
    expect(f.tasks()).toEqual([]);
    await f.cron(min(36));                             // nem nyit újat, nem ír újra
    expect(f.incidents()).toHaveLength(1);
    expect(f.mails).toHaveLength(1);
  });

  it('dead-man of another box: nobody can reach it in v1 → ember-kell, mail at once, then "Megoldva"', async () => {
    const f = await flottaApp();
    await f.report('beta', [green('szervezo')]);
    for (const t of [0, 20]) await f.report('gondnok', [green('gondnok')], min(t));
    await f.cron(min(31));
    expect(f.incidents().map(i => [i.subject, i.state])).toEqual([['box:beta', 'ember-kell']]);
    expect(f.tasks()).toEqual([]);
    expect(f.mails.map(m => m.subject)).toEqual(['Flotta-hiba: a beta box nem jelentett']);
    await f.report('beta', [green('szervezo')], min(35));
    await f.cron(min(36));
    expect(f.incidents()[0].status).toBe('resolved');
    expect(f.mails.at(-1)!.subject).toBe('Megoldva: a beta box nem jelentett');
  });

  it('a box that never reported trips the dead-man too', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [green('gondnok')], min(30));
    await f.cron(min(31));
    expect(f.incidents().map(i => i.subject)).toEqual(['box:beta']);
    expect(f.incidents()[0].detail).toMatch(/még soha nem jelentett/);
  });

  it('a failed send releases the claim and is retried on the next run, without duplicates', async () => {
    const f = await flottaApp();
    await f.report('gondnok', [red('gondnok', 'git')]);
    f.failResend(500);
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await f.cron(min(1));
    expect(f.mails).toEqual([]);
    expect(f.incidents()[0].mail_count).toBe(0);
    f.failResend(200);
    await f.cron(min(6));
    await f.cron(min(11));
    expect(f.mails).toHaveLength(1);
    const ev = f.raw.prepare('SELECT kind FROM flotta_incident_event ORDER BY id').all().map((e: any) => e.kind);
    expect(ev).toEqual(['opened', 'uncovered', 'mail_failed', 'mail_first']);
  });

  it('thresholds are configurable per fleet', async () => {
    const f = await flottaApp();
    f.raw.prepare(`UPDATE flotta_fleet SET escalate_min = 15, deadman_min = 10`).run();
    await f.report('beta', [red('vilma', 'kuldes')]);
    await f.report('gondnok', [green('gondnok')]);
    await f.cron(min(11));
    expect(f.incidents().map(i => i.subject)).toContain('box:beta');
    await f.cron(min(16));
    expect(f.mails.some(m => m.subject.includes('vilma'))).toBe(true);
    expect(T0.toISOString()).toBe('2026-11-07T10:00:00.000Z');
  });
});
