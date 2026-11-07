import { describe, expect, it, vi } from 'vitest';
import { task, show, stubApi, click, tick } from './testkit';
import { flatten, tree, today } from './meta';
import { TasksPage } from './TasksPage';
describe('task tree presentation', () => {
  it('keeps completed descendants in position under an open parent, excluding released branches', () => {
    const rows = [task,
      { ...task, id: 'first', parent_id: 'one', position: 'A', status: 'done' as const },
      { ...task, id: 'last', parent_id: 'one', position: 'Z', due_date: '2099-12-31' },
      { ...task, id: 'dropped', parent_id: 'one', status: 'dropped' as const },
      { ...task, id: 'hidden', parent_id: 'dropped' },
      { ...task, id: 'archived', parent_id: 'one', archived: 1 },
      { ...task, id: 'also-hidden', parent_id: 'archived' },
    ];
    const roots = tree(rows, true);
    expect(roots[0].children?.map(r => r.id)).toEqual(['first', 'last']);
    expect(flatten(tree(rows, false))).toHaveLength(rows.length);
  });
  it('rebuilds a flattened tree without duplicating existing children', () => {
    const rows = [task, { ...task, id: 'child', parent_id: 'one' }, { ...task, id: 'grandchild', parent_id: 'child' }];
    expect(flatten(tree(flatten(tree(rows, true)), false)).map(r => r.id)).toEqual(['one', 'child', 'grandchild']);
  });
  it('retains a newly completed root only for the current session', () => {
    const done = { ...task, status: 'done' as const };
    expect(tree([done], true)).toEqual([]);
    expect(tree([done], true, new Set(['one']))[0].id).toBe('one');
  });
  it('shows older non-repeating work behind a collapsed count-free row', async () => {
    const old = { ...task, id: 'old', title: 'Régi lépés', due_date: '2000-01-01' };
    stubApi(url => ({ body: url.endsWith('/principals') ? [] : [old] }));
    const { container } = await show('/feladatok', [['feladatok', <TasksPage />]]);
    const header = container.querySelector('.ant-collapse-header')!;
    expect(header.textContent?.trim()).toBe('Régebbről maradt');
    expect(header.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('a[href="/feladatok/old"]')).toBeNull();
    await click(header);
    expect(container.querySelector('a[href="/feladatok/old"]')?.textContent).toBe('Régi lépés');
  });
  it('keeps recurring work from the past in Most without duplicating it in older work', () => {
    const recurring = { ...task, due_date: '2000-01-01', repeat_rule: 'daily' };
    expect(tree([recurring], true)).toHaveLength(1);
    expect(tree([recurring], true, new Set(), true)).toHaveLength(0);
  });
  it('opens parents when data arrives, remembers collapsing, and reloads on visibility', async () => {
    const storage = new Map<string, string>();
    vi.stubGlobal('localStorage', { getItem: (k: string) => storage.get(k) ?? null, setItem: (k: string, v: string) => storage.set(k, v) });
    const rows = [task, { ...task, id: 'child', parent_id: 'one', due_date: today() }];
    const calls = stubApi(url => ({ body: url.endsWith('/principals') ? [] : rows }));
    const first = await show('/feladatok', [['feladatok', <TasksPage />]]);
    const expand = first.container.querySelector('.ant-table-row-expand-icon')!;
    expect(expand.getAttribute('aria-expanded')).toBe('true');
    await click(expand);
    expect(JSON.parse(storage.get('todo:expanded:Most')!).keys).toEqual([]);
    // Switching away and back remounts TaskTree, exercising persisted state.
    await click([...first.container.querySelectorAll('.ant-segmented-item')].find(e => e.textContent?.includes('Minden')));
    await click([...first.container.querySelectorAll('.ant-segmented-item')].find(e => e.textContent?.includes('Most')));
    expect(first.container.querySelector('.ant-table-row-expand-icon')?.getAttribute('aria-expanded')).toBe('false');
    const before = calls.length;
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    document.dispatchEvent(new Event('visibilitychange'));
    await tick(100);
    expect(calls.length).toBeGreaterThan(before);
  });
  it('keeps completed roots visible and provides revision-safe undo', async () => {
    let row = { ...task };
    const calls = stubApi((url, method) => {
      if (url.endsWith('/complete')) { row = { ...row, status: 'done', rev: 4 }; return { body: row }; }
      if (method === 'PATCH') { row = { ...row, status: 'open', rev: 5 }; return { body: row }; }
      return { body: url.endsWith('/principals') ? [] : [row] };
    });
    const { container } = await show('/feladatok', [['feladatok', <TasksPage />]]);
    await click(container.querySelector('input[type="checkbox"]')!);
    expect(container.querySelector('.todo-done')).toBeTruthy();
    await click([...document.querySelectorAll('button')].find(b => b.textContent?.includes('Visszavonom')));
    expect(calls.find(c => c.method === 'PATCH')?.body).toEqual({ expected_rev: 4, set: { status: 'open' } });
    expect(container.querySelector('.todo-done')).toBeNull();
  });
});
