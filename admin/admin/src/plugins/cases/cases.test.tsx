import { afterEach, describe, expect, it, vi } from 'vitest';
import { CaseListPage } from './CaseListPage';
import { CaseShowPage } from './CaseShowPage';
import { stubApi, show, button, click, type } from './testkit';
import { newUlid } from './ulid';
import { recurrenceLabel } from './meta';

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
});

const GAS = '01JAB6Z9Q3M8K7T2V5W4X1Y0RS';
const gas = {
  id: GAS, title: 'Gázszámla', status: 'open', description: 'A havi gázszámla.', next_action: 'Átutalás',
  due_at: '2026-09-10', recurrence: 'monthly:10', anchor_at: '2026-09-10',
  brain_ref: 'agy/cases/gazszamla.md', context: '# Gázszámla\nA számítás itt van.', context_hash: 'x',
  extra: {}, version: 3, created_at: '', updated_at: '',
};
const detail = { ...gas, occurrences: [], open_occurrences: ['2026-09-10', '2026-10-10'], events: [] };

describe('case list', () => {
  it('lists cases by due date, with status and recurrence in words', async () => {
    stubApi(() => ({ body: [gas, { ...gas, id: 'b', title: 'Kárigény', status: 'waiting', recurrence: null, due_at: '2099-01-01' }] }));
    const { container } = await show('/ugyek', [['ugyek', <CaseListPage />]]);
    const rows = [...container.querySelectorAll('tbody tr')].map((r) => r.textContent);
    expect(rows[0]).toContain('Gázszámla');
    expect(rows[0]).toContain('havonta 10-én');
    expect(rows[0]).toContain('lejárt');
    expect(rows[1]).toContain('várakozik');
  });

  it('creates a case with a PUT to a fresh ULID', async () => {
    const calls = stubApi((_u, method) => (method === 'PUT' ? { status: 201, body: gas } : { body: [] }));
    await show('/ugyek', [['ugyek', <CaseListPage />]]);
    await click(button('Új ügy')[0]);
    await type('input#title', 'Adóbevallás');
    await type('textarea#description', 'Az éves SZJA.');
    await type('input#due_at', '2027-05-20');
    await click(button('Mentés')[0]);
    const put = calls.find((c) => c.method === 'PUT')!;
    expect(put.url).toMatch(/\/api\/cases\/[0-7][0-9A-HJKMNP-TV-Z]{25}$/);
    expect(put.body).toMatchObject({ title: 'Adóbevallás', description: 'Az éves SZJA.', due_at: '2027-05-20', status: 'open' });
    expect(put.body).not.toHaveProperty('waiting_on');
    expect(put.body).not.toHaveProperty('version');
  });
});

// The instance's own field (config/models.json → GET /api/meta): no screen code.
const PRIORITY = { name: 'priority', label: 'Prioritás', type: 'select', options: ['alacsony', 'magas'] };
const withPriority = (body: unknown) => (url: string) =>
  url.endsWith('/api/meta') ? { body: { fields: { cases: [PRIORITY] }, entities: [] } } : { body };

describe('own case fields', () => {
  it('shows a declared field as a list column', async () => {
    stubApi(withPriority([{ ...gas, priority: 'magas' }]));
    const { container } = await show('/ugyek', [['ugyek', <CaseListPage />]]);
    expect([...container.querySelectorAll('th')].map((t) => t.textContent)).toContain('Prioritás');
    expect(container.querySelector('tbody tr')!.textContent).toContain('magas');
  });

  it('keeps it on an edit, and leaves out a field still pending its migration', async () => {
    const calls = stubApi((url, method) =>
      method === 'PUT'
        ? { body: detail }
        : url.endsWith('/api/meta')
          ? { body: { fields: { cases: [PRIORITY, { name: 'osszeg', label: 'Összeg', type: 'number', pending: true }] }, entities: [] } }
          : { body: { ...detail, priority: 'magas' } },
    );
    const { container } = await show(`/ugyek/${GAS}`, [['ugyek/:id', <CaseShowPage />]]);
    expect(container.textContent).toContain('Prioritás');
    expect(container.textContent).not.toContain('Összeg');
    await click(button('Szerkesztés')[0]);
    await click(button('Mentés')[0]);
    const put = calls.find((c) => c.method === 'PUT')!;
    expect(put.body).toMatchObject({ priority: 'magas', version: 3 });
    expect(put.body).not.toHaveProperty('osszeg');
  });
});

describe('case detail', () => {
  it('shows the brain context and offers closing only the earliest open occurrence', async () => {
    const calls = stubApi(() => ({ body: detail }));
    const { container } = await show(`/ugyek/${GAS}`, [['ugyek/:id', <CaseShowPage />]]);
    expect(container.textContent).toContain('A számítás itt van.');
    expect(container.textContent).toContain('2026-10-10');
    expect(button('Lezárás')).toHaveLength(1);
    await click(button('Lezárás')[0]);
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.url).toMatch(new RegExp(`/api/cases/${GAS}/occurrences$`));
    expect(post.body).toMatchObject({ due_at: '2026-09-10', status: 'done' });
    expect((post.body as { done_at: string }).done_at).toMatch(/^\d{4}-\d\d-\d\d$/);
  });

  it('edits with the version it read, leaving a recurring due date to the server', async () => {
    const calls = stubApi((_u, method) => (method === 'PUT' ? { body: { ...detail, version: 4 } } : { body: detail }));
    await show(`/ugyek/${GAS}`, [['ugyek/:id', <CaseShowPage />]]);
    await click(button('Szerkesztés')[0]);
    await type('input#next_action', 'Csekk helyett átutalás');
    await click(button('Mentés')[0]);
    const put = calls.find((c) => c.method === 'PUT')!;
    expect(put.body).toMatchObject({ version: 3, next_action: 'Csekk helyett átutalás', recurrence: 'monthly:10' });
    expect(put.body).not.toHaveProperty('due_at');
    expect(put.body).not.toHaveProperty('context');
  });

  it('says so when someone else changed the case first (409)', async () => {
    stubApi((_u, method) =>
      method === 'PUT' ? { status: 409, body: { error: 'version conflict — re-read the case', version: 4 } } : { body: detail },
    );
    await show(`/ugyek/${GAS}`, [['ugyek/:id', <CaseShowPage />]]);
    await click(button('Szerkesztés')[0]);
    await type('input#title', 'Gáz');
    await click(button('Mentés')[0]);
    expect(document.body.textContent).toMatch(/Ütközés.*version conflict/);
  });
});

describe('newUlid', () => {
  it('makes 26-char Crockford ULIDs that sort by time', () => {
    const a = newUlid(1_700_000_000_000);
    const b = newUlid(1_700_000_000_001);
    expect(a).toMatch(/^[0-7][0-9A-HJKMNP-TV-Z]{25}$/);
    expect(a < b).toBe(true);
  });
});

describe('recurrenceLabel', () => {
  it('says every rule in words, the quarterly one too', () => {
    expect(recurrenceLabel('monthly:10')).toBe('havonta 10-én');
    expect(recurrenceLabel('quarterly:20')).toBe('negyedévente 20-án');
    expect(recurrenceLabel('yearly:05-20')).toBe('évente 05.20.');
  });

  it('lists a quarterly case in words', async () => {
    stubApi(() => ({ body: [{ ...gas, recurrence: 'quarterly:20', anchor_at: '2026-01-20', due_at: '2099-01-20' }] }));
    const { container } = await show('/ugyek', [['ugyek', <CaseListPage />]]);
    expect(container.querySelector('tbody tr')!.textContent).toContain('negyedévente 20-án');
  });
});
