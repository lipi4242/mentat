import { tick } from '../../test-render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { stubApi, show as showPage, button, click, type } from '../cases/testkit';
import { TasksPage } from './TasksPage';
import { TaskPage } from './TaskPage';
import { LabelsPage } from './LabelsPage';
import { PrincipalsPage } from './PrincipalsPage';
import { MoveTask } from './MoveTask';
import { possibleParents, tree, relativeTime, today, type Detail } from './meta';

async function enter(label: string) {
  document.querySelector(`input[aria-label="${label}"]`)!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
  document.querySelector(`input[aria-label="${label}"]`)!.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
  await tick(150);
}
vi.mock('../../lib/authClient', () => ({ authClient: { getSession: vi.fn(async () => ({ data: { user: { email: 'owner@example.com' } } })) } }));
const unmounts: Array<() => void> = [];
async function show(...args: Parameters<typeof showPage>) {
  const view = await showPage(...args);
  unmounts.push(view.unmount);
  return view;
}
afterEach(() => {
  // Unmount forms before jsdom disappears so their debounce timers are cancelled.
  for (const unmount of unmounts.splice(0)) unmount();
  vi.unstubAllGlobals(); document.body.innerHTML = '';
});
const task: Detail = { id: 'one', title: 'Reggeli rutin', description: 'Egy lépés', parent_id: null, position: 'U', status: 'open', due_date: null,
  due_time: null, planned_date: null, tz: 'Europe/Budapest', owner_id: 'p', assignee_id: null, assignee_note: null,
  repeat_rule: null, repeat_from: 'schedule', progress: null, archived: 0, rev: 3, children: [], labels: [], comments: [] };
const principal = { id: 'p', kind: 'human', handle: 'owner', display_name: 'Gipsz Jakab', disabled_at: null };
const detailRoute = (url: string) => url.endsWith('/tasks') ? { body: [task] } : url.endsWith('/principals') ? { body: [principal] } : url.endsWith('/labels') ? { body: [{ id: 'l', name: 'Otthon' }] } : { body: task };

describe('todo task tree', () => {
  it('displays server progress even when descendant rows are not in the response', async () => {
    stubApi(() => ({ body: [{ ...task, progress: { done: 2, total: 3, percent: 67 } }] }));
    const { container } = await show('/feladatok', [['feladatok', <TasksPage />]]);
    const progress = container.querySelector('[role="progressbar"]');
    expect(progress?.getAttribute('aria-valuenow')).toBe('67');
    expect(progress?.textContent).toBe('2/3');
    expect(container.querySelector('input[type="checkbox"]')?.hasAttribute('checked')).toBe(false);
  });
  it('keeps ancestor context without surfacing old dates in the default view', async () => {
    stubApi(() => ({ body: [{ ...task, due_date: '2000-01-01' }, { ...task, id: 'child', parent_id: task.id, title: 'Mai lépés', due_date: today() }, { ...task, id: 'past', title: 'Régi', due_date: '2000-02-01' }] }));
    const { container } = await show('/feladatok', [['feladatok', <TasksPage />]]);
    expect(container.textContent).toContain('Reggeli rutin'); expect(container.textContent).not.toContain('Régi');
    expect(container.textContent).toContain('Mai lépés');
    const date = container.querySelector('.todo-due [aria-label="history"]');
    expect(date).toBeTruthy(); expect(container.textContent).not.toContain('lejárt');
    await click([...container.querySelectorAll('.ant-segmented-item')].find(e => e.textContent === 'Minden'));
    expect(container.textContent).toContain('Régi');
  });
  it('retries root creation with the same idempotency key', async () => {
    let attempt = 0;
    const calls = stubApi((_url, method) => method === 'POST' ? (++attempt === 1 ? { status: 500, body: {} } : { body: task }) : { body: [] });
    await show('/feladatok', [['feladatok', <TasksPage />]]);
    await type('input[aria-label="Feladat címe"]', 'Kis lépés');
    await enter('Feladat címe'); await enter('Feladat címe');
    const writes = calls.filter(c => c.method === 'POST');
    expect(writes).toHaveLength(2); expect(writes[0].body).toEqual(writes[1].body);
    expect(writes[0].body).toMatchObject({ title: 'Kis lépés', parent_id: null, idem_key: expect.any(String) });
  });
  it('quick-adds under a row and completes with its revision', async () => {
    const calls = stubApi((_url, method) => ({ body: method === 'POST' ? task : [task] }));
    const { container } = await show('/feladatok', [['feladatok', <TasksPage />]]);
    await click(container.querySelector('button[aria-label="Részfeladat"]')!); await type('input[aria-label="Részfeladat címe"]', 'Részlépés'); await enter('Részfeladat címe');
    expect(calls.find(c => c.method === 'POST')!.body).toMatchObject({ parent_id: 'one' });
    await click(container.querySelector('input[type="checkbox"]')!);
    expect(calls.find(c => c.url.endsWith('/complete'))!.body).toEqual({ expected_rev: 3 });
  });
  it('moves with a parent picker and the displayed revision', async () => {
    const calls = stubApi(() => ({ body: task }));
    await show('/move', [['move', <MoveTask row={task} rows={[task]} onSaved={() => {}} onClose={() => {}} />]]);
    await click(button('Áthelyezés').at(-1));
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: '/api/todo/v1/tasks/one/move', body: { parent_id: null, expected_rev: 3 } });
    expect(possibleParents([task, { ...task, id: 'child', parent_id: 'one' }, { ...task, id: 'grand', parent_id: 'child' }, { ...task, id: 'other' }], 'one').map(r => r.id)).toEqual(['other']);
  });
});

describe('todo detail', () => {
  it.each([{ done: 1, total: 1, percent: 100 }, { done: 0, total: 0, percent: 0 }])('shows neutral parent progress %j independently of completion', async progress => {
    stubApi(url => url.endsWith('/tasks/one') ? { body: { ...task, progress } } : detailRoute(url));
    const { container } = await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    expect(container.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe(String(progress.percent));
    expect(container.textContent).toContain(`${progress.percent}% · ${progress.done}/${progress.total}`);
    expect(container.querySelector('.ant-progress-status-success')).toBeNull();
    expect(container.querySelector('button[aria-label="Kész"]')).toBeTruthy();
  });
  it('edits fields using expected_rev and reports stale revisions', async () => {
    const calls = stubApi((url, method) => method === 'PATCH' ? { status: 409, body: { error: 'revision conflict', current: { ...task, rev: 4 } } } : detailRoute(url));
    await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    await click(document.querySelector('button[aria-label="Határidő"]')!);
    await type('input[aria-label="Határidő napja"]', '2026-11-01');
    await click(document.querySelector('button[aria-label="Határidő"]')!);
    expect(calls.find(c => c.method === 'PATCH')!.body).toEqual({ expected_rev: 3, set: { due_date: '2026-11-01' } });
    expect(document.body.textContent).toContain('Közben valaki módosította, frissítettem.');
    expect(document.querySelector('[role="progressbar"]')).toBeNull();
  });
  it('shows avatar/name/relative time and sends revision-bound comments and labels', async () => {
    const comment = { id: 'c', display_name: 'Thufir', avatar: null, kind: 'agent', handle: 'thufir', body: 'Itt vagyok.', created_at: new Date(Date.now() - 120000).toISOString() };
    const calls = stubApi((url, method) => method === 'POST' ? { body: task } : url.endsWith('/tasks/one') ? { body: { ...task, comments: [comment] } } : detailRoute(url));
    const { container } = await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    expect(container.textContent).toContain('Thufir'); expect(container.textContent).toContain('Itt vagyok.');
    expect(container.textContent).toContain('2 perccel ezelőtt'); expect(container.querySelector('.ant-avatar')).toBeTruthy();
    await type('textarea[aria-label="Új komment"]', '@owner Kész a lépés'); await click(container.querySelector('button[aria-label="Küldés"]')!);
    expect(calls.find(c => c.url.endsWith('/comments'))!.body).toMatchObject({ body: '@owner Kész a lépés', expected_rev: 3 });
    expect(container.querySelector('[aria-label="Ágens"]')).toBeTruthy();
    await click(container.querySelector('button[aria-label="Címkék"]')!);
    await click(container.querySelector('button[aria-label="Címkék"]')!);
    expect(calls.some(c => c.method === 'POST' && c.url.endsWith('/labels'))).toBe(false);
  });
});

describe('todo catalogs', () => {
  it('creates and lists labels with an idempotency key', async () => {
    const calls = stubApi((_url, method) => ({ body: method === 'POST' ? {} : [{ id: 'l', name: 'Otthon', color: '#888888' }] }));
    const { container } = await show('/feladat-cimkek', [['feladat-cimkek', <LabelsPage />]]);
    expect(container.textContent).toContain('Otthon');
    await type('input#name', 'Munka'); await click(button('Címke hozzáadása')[0]);
    expect(calls.find(c => c.method === 'POST')!.body).toMatchObject({ name: 'Munka', idem_key: expect.any(String) });
  });
  it('allows self-bootstrap even while the principal list is forbidden', async () => {
    const calls = stubApi((_url, method) => method === 'POST' ? { status: 201, body: principal } : { status: 403, body: {} });
    await show('/resztvevok', [['resztvevok', <PrincipalsPage />]]);
    await click(button('Hozzáadás')[0]);
    await type('input#display_name', 'Gipsz Jakab'); await type('input#handle', 'owner'); await type('input#auth_email', 'owner@example.com');
    await click(button('Résztvevő hozzáadása')[0]);
    expect(calls.find(c => c.method === 'POST')!.body).toMatchObject({ kind: 'human', auth_email: 'owner@example.com', agent_token_id: null, idem_key: expect.any(String) });
  });
});

describe('supportive presentation', () => {
  it('keeps dropped work in All and renders relative time', () => {
    const dropped = { ...task, status: 'dropped' as const };
    expect(tree([dropped], true)).toEqual([]); expect(tree([dropped], false)).toHaveLength(1);
    expect(relativeTime(new Date().toISOString())).toBe('most');
  });
});
