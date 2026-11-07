// The UI against the REAL worker routes (in-memory D1 from worker/__tests__), not a mock:
// issue → take → submit (as the developer, straight on the API) → accept (through the UI).
import { vi, afterEach, describe, expect, it } from 'vitest';
import { show, button, click, tick } from '../todo/testkit';
import { ItemPage } from './ItemPage';
import { ProjectPage } from './ProjectPage';

const worker = (rel: string) => new URL(`../../../../worker/${rel}`, import.meta.url).pathname;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });

async function boot() {
  const load = (p: string) => import(/* @vite-ignore */ p);
  const fixture = await load(worker('__tests__/backlog-fixture.ts')), { default: app } = await load(worker('src/index.ts'));
  const t = await fixture.backlogApp();
  // The signed-in "person" in the UI is PM agent `a`; every UI fetch goes to the real app.
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) =>
    app.request(url, { ...init, headers: { ...(init.headers as object), 'X-Mentat-Token': 'a' } }, t.env)));
  return t;
}
const tickAll = async () => { await tick(100); };

describe('UI against the real worker', () => {
  it('PM accepts a submitted round through the page', async () => {
    const t = await boot();
    const row = await t.item();
    await t.act(row.id, 'issue', { dev: 'b' }); await t.act(row.id, 'take', {}, 'b'); await t.submit(row.id);
    await show('/tetel/WEB-1', [['tetel/:id', <ItemPage />]]); await tickAll();
    expect(button('Elfogadás')[0].hasAttribute('disabled')).toBe(true);
    for (const box of document.querySelectorAll<HTMLInputElement>('.bl-results input[type=checkbox]')) await click(box);
    await click(button('Elfogadás')[0]); await tickAll();
    expect((await t.get(row.id)).stage).toBe('done');
    expect((await t.get(row.id)).reports[0].results.every((r: { pm_ok: number }) => r.pm_ok === 1)).toBe(true);
  });
  it('reject sends a note per failing AC and the real worker takes it', async () => {
    const t = await boot();
    const row = await t.item();
    await t.act(row.id, 'issue', { dev: 'b' }); await t.act(row.id, 'take', {}, 'b'); await t.submit(row.id);
    await show('/tetel/WEB-1', [['tetel/:id', <ItemPage />]]); await tickAll();
    await click(document.querySelectorAll<HTMLInputElement>('.bl-results input[type=checkbox]')[0]);
    const { type } = await import('../todo/testkit');
    await type('input[aria-label^="Megjegyzés"]', 'Hiányzik a teszt');
    await click(button('Visszautasítás')[0]); await tickAll();
    expect((await t.get(row.id)).stage).toBe('taken');
  });
  it('project list move uses a position the real worker accepts', async () => {
    const t = await boot();
    const [x, y] = [await t.item({ title: 'X' }), await t.item({ title: 'Y' })];
    await show('/projekt/WEB', [['projekt/:id', <ProjectPage />]]); await tickAll();
    await click(document.querySelector(`button[aria-label="WEB-2 mozgatása"]`)!);
    document.querySelector('.ant-select-selector')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await tick(50);
    await click([...document.querySelectorAll('.ant-select-item-option')].find(o => o.textContent?.includes('WEB-1')));
    await click([...document.querySelectorAll('.ant-modal-footer button')].find(b => b.textContent === 'Áthelyezés')); await tickAll();
    expect((await t.get(y.id)).position < (await t.get(x.id)).position).toBe(true);
  });
});
