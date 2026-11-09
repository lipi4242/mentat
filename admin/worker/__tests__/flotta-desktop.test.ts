// paritás: a saját gépen (Claude Desktop/Code, nincs always-on processz, nincs híd)
// futó ágens ugyanúgy javítási CÉL és ugyanúgy menedzser lehet, amíg a sessionje fut és jelent.
// Ami csak boxon értelmes: a csend mint hiba (dead-man) és a gép teljes kiesése mint tartomány.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flottaApp, green, min, red } from './flotta-fixture';
import { DESKTOP_FRESH_MIN } from '../src/plugins/flotta/managers';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const desktop = async () => {
  const f = await flottaApp();
  f.raw.prepare(`UPDATE flotta_box SET kind = 'desktop' WHERE name = 'beta'`).run();
  f.manager('p-helyettes', 'helyettes', '*', 2);
  return f;
};

describe('desktop machines', () => {
  it('a silent desktop opens no dead-man incident and is not a box-level coverage gap', async () => {
    const f = await desktop();
    await f.report('gondnok', [green('gondnok')], min(40));
    await f.cron(min(41));
    expect(f.incidents()).toEqual([]);                        // egy box ugyanennyi csend után dead-man lenne
    const s = await f.report('beta', [green('helyettes')], min(45));
    expect(s.body.coverage.uncovered.map((u: any) => u.target)).not.toContain('box:beta');
  });

  it('a desktop agent reported red by its own session is a repair target; a desktop manager repairs while its session reports', async () => {
    const f = await desktop();
    await f.report('beta', [green('helyettes'), red('laptop-agens', 'todo')]);
    expect(f.incidents()[0]).toMatchObject({ subject: 'agent:laptop-agens', state: 'kiosztva', assigned_principal_id: 'p-helyettes' });
    const c = await f.call('POST', `/api/flotta/v1/incidents/${f.incidents()[0].id}/claim`, {}, 'plain-helyettes-agent', min(2));
    expect(c.status).toBe(200);
  });

  it('a desktop manager whose session stopped reporting is unfit (no always-on response time)', async () => {
    const f = await desktop();
    await f.report('beta', [green('helyettes')]);
    await f.report('beta', [red('laptop-agens', 'git')], min(31));   // a helyettes sessionje már nem jelent
    expect(f.incidents()[0].state).toBe('ember-kell');
  });

  it('the Worker itself refuses restart steps on a desktop target (box kind OR the agent\'s own desktop flag); no budget is spent', async () => {
    for (const via of ['box', 'agent'] as const) {
      const f = await flottaApp();
      f.manager('p-helyettes', 'helyettes', '*', 2);
      if (via === 'box') f.raw.prepare(`UPDATE flotta_box SET kind = 'desktop' WHERE name = 'beta'`).run();
      const laptop = { ...red('laptop-agens', 'todo'), desktop: via === 'agent' };
      await f.report('beta', [green('helyettes'), laptop]);
      const id = f.incidents()[0].id;
      const c = (await f.call('POST', `/api/flotta/v1/incidents/${id}/claim`, {}, 'plain-helyettes-agent', min(1))).body;
      const b = { fence: c.fence, claim: c.claim, step: 'doctor-fix', target: 'agent:laptop-agens' };
      const r = await f.call('POST', `/api/flotta/v1/incidents/${id}/ops/op-desk-0001/intent`, b, 'plain-box-beta', min(2));
      expect([via, r.status, r.body.code]).toEqual([via, 409, 'desktop']);
      expect(f.raw.prepare('SELECT count(*) AS n FROM flotta_restart_budget').get()).toEqual({ n: 0 });
      const d = await f.call('POST', `/api/flotta/v1/incidents/${id}/ops/check`, { ...b, step: 'doctor', op_id: 'op-desk-0002' }, 'plain-box-beta', min(2));
      expect(d.status).toBe(200);
    }
  });

  it('a desktop manager is fit only within DESKTOP_FRESH_MIN of its last session report, not the box dead-man window', async () => {
    const f = await desktop();
    f.raw.prepare('UPDATE flotta_fleet SET deadman_min = 100000').run();
    await f.report('beta', [green('helyettes')]);
    await f.report('beta', [red('laptop-agens', 'git')], min(DESKTOP_FRESH_MIN + 1));
    expect(f.incidents()[0].state).toBe('ember-kell');            // a box-ablak (100000 p) itt nem számít
  });
});

