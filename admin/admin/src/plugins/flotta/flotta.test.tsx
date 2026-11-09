import { afterEach, describe, expect, it, vi } from 'vitest';
import { click, show as showPage, stubApi } from '../cases/testkit';
import { FlottaPage } from './FlottaPage';
import { age, type Status } from './meta';

const unmounts: Array<() => void> = [];
async function show(...args: Parameters<typeof showPage>) {
  const view = await showPage(...args); unmounts.push(view.unmount); return view;
}
afterEach(() => { for (const u of unmounts.splice(0)) u(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });

const status: Status = {
  now: '2026-11-07T10:40:00Z',
  fleets: [{ id: 'default', name: 'Flotta', managers: [{ id: 'm1', principal_id: 'p', agent: 'gondnok', scope: '*', rank: 1, handle: 'gondnok', disabled_at: null },
    { id: 'm2', principal_id: 'q', agent: 'helyettes', scope: 'beta', rank: 2, handle: 'helyettes', disabled_at: null }], effective_owner_email: 'owner@example.com',
    deadman_min: 30, escalate_min: 60, debounce_reports: 2, repeat_min: 360 }],
  boxes: [
    { id: 'b1', name: 'gondnok', fleet_id: 'default', last_report_at: '2026-11-07T10:35:00Z', age_min: 5, stale: false, fleet_version: '1.4.0', disabled_at: null,
      release: { here: 'v0.5.0', latest: 'v0.5.1', lag: 'régebbi' } },
    { id: 'b2', name: 'beta', fleet_id: 'default', last_report_at: null, age_min: null, stale: true, fleet_version: null, disabled_at: null, release: null, rejected_count: 3, last_reject: 'cross-box' },
  ],
  agents: [{ id: 'a', name: 'vilma', box_name: 'gondnok', last_seen_at: '2026-11-07T10:35:00Z', measured_at: '2026-11-07T10:30:00Z',
    result: { red: [{ check: 'kuldes', detail: 'nincs token' }], unknown: [], ok: ['git'] } }],
  incidents: [{ id: 'i1', subject: 'agent:vilma', agent: 'vilma', check_key: 'kuldes', status: 'open', detail: 'nincs token', box_name: 'gondnok',
    opened_at: '2026-11-07T10:00:00Z', resolved_at: null, resolve_note: null, red_count: 3, mail_count: 1, todo_task_id: 'T1' }],
};

describe('flotta page', () => {
  it('shows boxes with report age, agents with red checks, incidents with the task link and history', async () => {
    const calls = stubApi(url => url.endsWith('/status') ? { body: status }
      : { body: { ...status.incidents[0], events: [{ id: 1, at: '2026-11-07T10:00:00Z', kind: 'opened', body: null }, { id: 2, at: '2026-11-07T11:01:00Z', kind: 'mail_first', body: null }] } });
    const { container } = await show('/flotta', [['flotta', <FlottaPage />]]);
    const text = container.textContent!;
    expect(text).toContain('Felelős ágensek1. gondnok (minden) · 2. helyettes (beta)');
    expect(text).toContain('5 perce');
    expect(text).toContain('néma');
    expect(text).toContain('soha');
    expect(text).toContain('elutasítva 3×');
    expect(text).toContain('kuldes');
    expect(container.querySelector('a[href="/feladatok/T1"]')).not.toBeNull();
    await click(container.querySelector('.ant-table-row-expand-icon') ?? undefined);
    expect(calls.some(c => c.url.endsWith('/api/flotta/v1/incidents/i1'))).toBe(true);
    expect(container.textContent).toContain('e-mail a tulajdonosnak');
  });

  it('says plainly when there is no responsible agent', async () => {
    stubApi(() => ({ body: { ...status, fleets: [{ ...status.fleets[0], managers: [] }] } }));
    const { container } = await show('/flotta', [['flotta', <FlottaPage />]]);
    expect(container.textContent).toContain('nincs — a hiba e-mailben megy');
  });

  it('formats ages', () => {
    expect([age(null), age(0), age(12), age(130), age(3000)]).toEqual(['soha', 'most', '12 perce', '2 órája', '2 napja']);
  });
});
