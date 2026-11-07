import { describe, expect, it } from 'vitest';
import { stubApi, show, button, click, type, tick } from '../todo/testkit';
import { BallPage } from './BallPage';
import { ItemPage } from './ItemPage';
import { ProjectPage } from './ProjectPage';
import type { ItemDetail, Result } from './meta';

const people = [{ id: 'h', kind: 'human', handle: 'jakab', display_name: 'Gipsz Jakab', disabled_at: null, avatar: null },
  { id: 'd', kind: 'agent', handle: 'dev', display_name: 'Fejlesztő', disabled_at: null, avatar: null }];
const res = (id: string, verdict: Result['verdict'] = 'met'): Result => ({ ac_id: id, ac_text: `Feltétel ${id}`, verdict, evidence: 'lásd PR', pm_ok: null, pm_note: null });
const item = (over: Partial<ItemDetail> = {}): ItemDetail => ({ id: 'i1', key: 'WEB-1', project_id: 'prj', title: 'Minta tétel', stage: 'draft', priority: 0,
  owner_id: 'h', assignee_id: null, dev_id: null, parent_id: null, position: 'U', rev: 4, description: null, request_quote: null,
  acs: [{ id: 'a1', text: 'Feltétel a1', position: 'U' }], links: [], reports: [], comments: [], ...over });
const route = (it: ItemDetail, me = people[0]) => (url: string) => ({ body: url.endsWith('/me') ? me : url.endsWith('/principals') ? people : it });
const page = () => show('/tetel/WEB-1', [['tetel/:id', <ItemPage />]]);
async function pick(text: string) {
  document.querySelector('.ant-select-selector')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await tick(50);
  await click([...document.querySelectorAll('.ant-select-item-option')].find(o => o.textContent?.includes(text)));
}
const labels = () => [...document.querySelectorAll('button')].map(b => b.textContent);
const review = (reports = [{ id: 'r1', round: 1, summary: 'Kész', body: null, head_sha: null, submitted_at: '', pm_verdict: null as null,
  results: [res('a1'), res('a2')] }]) => item({ stage: 'review', reports, assignee_id: null, dev_id: 'd' });

describe('item page', () => {
  it('draft: PM sees issue/hold/drop, and issue sends the dev and expected_rev', async () => {
    const calls = stubApi(route(item()));
    await page();
    expect(labels()).toEqual(expect.arrayContaining(['Kiadás', 'Félretétel', 'Elvetés']));
    expect(labels()).not.toContain('Elfogadás');
    await click(button('Kiadás')[0]);
    const ok = () => [...document.querySelectorAll<HTMLButtonElement>('.ant-modal-footer button')].find(b => b.textContent === 'Kiadás')!;
    expect(ok().disabled).toBe(true);
    await pick('Fejlesztő');
    await click(ok());
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: expect.stringContaining('/items/i1/issue'), body: { dev: 'dev', expected_rev: 4 } });
  });
  it('hides issue (disabled) without an AC and shows no button to a stranger', async () => {
    stubApi(route(item({ acs: [] })));
    await page();
    expect(button('Kiadás')[0].hasAttribute('disabled')).toBe(true);
    document.body.innerHTML = '';
    stubApi(route(item({ stage: 'issued' }), { ...people[1], id: 'x', handle: 'x' }));
    await page();
    expect(document.querySelectorAll('.bl-actions button').length).toBe(0);
  });
  it('drop needs a note, then posts it with expected_rev', async () => {
    const calls = stubApi(route(item()));
    await page();
    await click(button('Elvetés')[0]);
    await type('textarea', 'Már nem kell');
    await click([...document.querySelectorAll('.ant-modal-footer button')].find(b => b.textContent === 'Elvetés'));
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: expect.stringContaining('/items/i1/drop'), body: { note: 'Már nem kell', expected_rev: 4 } });
  });
  it('review: accept is locked until every AC is ticked, then sends checks', async () => {
    const calls = stubApi(route(review()));
    await page();
    expect(button('Elfogadás')[0].hasAttribute('disabled')).toBe(true);
    for (const box of document.querySelectorAll<HTMLInputElement>('.bl-results input[type=checkbox]')) await click(box);
    expect(button('Elfogadás')[0].hasAttribute('disabled')).toBe(false);
    await click(button('Elfogadás')[0]);
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: expect.stringContaining('/items/i1/accept'),
      body: { expected_rev: 4, checks: [{ ac_id: 'a1', pm_ok: true }, { ac_id: 'a2', pm_ok: true }] } });
  });
  it('review: a not_met result can never be accepted, only sent back with a note', async () => {
    const calls = stubApi(route(review([{ id: 'r1', round: 1, summary: 'Majdnem', body: null, head_sha: null, submitted_at: '', pm_verdict: null,
      results: [res('a1'), res('a2', 'not_met')] }])));
    await page();
    for (const box of document.querySelectorAll<HTMLInputElement>('.bl-results input[type=checkbox]')) await click(box);
    expect(button('Elfogadás')[0].hasAttribute('disabled')).toBe(true);
    await click(box1());
    expect(button('Visszautasítás')[0].hasAttribute('disabled')).toBe(true);
    await type('input[aria-label="Megjegyzés: Feltétel a2"]', 'Hiányzik a teszt');
    await click(button('Visszautasítás')[0]);
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: expect.stringContaining('/reject'),
      body: { expected_rev: 4, note: 'Hiányzik a teszt', checks: [{ ac_id: 'a1', pm_ok: true }, { ac_id: 'a2', pm_ok: false, pm_note: 'Hiányzik a teszt' }] } });
  });
});
function box1() { return document.querySelectorAll<HTMLInputElement>('.bl-results input[type=checkbox]')[1]; }

describe('project list', () => {
  const rows = ['U', 'V', 'W'].map((p, n) => ({ ...item({ id: `i${n}`, key: `WEB-${n + 1}`, title: `Tétel ${n + 1}`, position: p, rev: n + 1 }) }));
  it('moves an item above another with a position between its neighbours and the item rev', async () => {
    const calls = stubApi(() => ({ body: rows }));
    await show('/projekt/WEB', [['projekt/:id', <ProjectPage />]]);
    await click(document.querySelector('button[aria-label="WEB-3 mozgatása"]')!);
    await pick('WEB-2');
    await click([...document.querySelectorAll('.ant-modal-footer button')].find(b => b.textContent === 'Áthelyezés'));
    const move = calls.find(c => c.method === 'POST') as { url: string; body: { position: string; expected_rev: number } };
    expect(move.url).toContain('/tasks/i2/move');
    expect(move.body.expected_rev).toBe(3);
    expect(move.body.position > 'U' && move.body.position < 'V').toBe(true);
  });
});

describe('ball page', () => {
  it('lists all three kinds under whoever holds the ball', async () => {
    stubApi(url => ({ body: url.endsWith('/principals') ? people
      : url.endsWith('/items') ? [item({ assignee_id: 'd', stage: 'issued' })]
      : [{ id: 't1', title: 'Hívd fel', status: 'open', archived: 0, owner_id: 'h', assignee_id: null },
        { id: 'c1', title: 'Biztosítás', kind: 'case', status: 'open', archived: 0, owner_id: 'h', assignee_id: null }] }));
    await show('/labda', [['labda', <BallPage />]]);
    const mine = document.querySelector('section[aria-label="Gipsz Jakab"]')!, theirs = document.querySelector('section[aria-label="Fejlesztő"]')!;
    expect(mine.textContent).toContain('Hívd fel'); expect(mine.textContent).toContain('Ügy');
    expect(theirs.textContent).toContain('WEB-1'); expect(theirs.textContent).toContain('Kiadva');
  });
});
