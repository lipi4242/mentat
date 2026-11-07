import { describe, expect, it, vi } from 'vitest';
import { task, principal, detailRoute, show, stubApi, type, click, key, tick } from './testkit';
import { TaskPage } from './TaskPage';
vi.mock('../../lib/authClient', () => ({ authClient: { getSession: vi.fn(async () => ({ data: { user: { email: 'owner@example.com' } } })) } }));
describe('inline task editing', () => {
  it('keeps unsaved TaskFields through comment reload and uses the new revision on close', async () => {
    let row = { ...task };
    const calls = stubApi((url, method, body) => {
      if (method === 'POST' && url.endsWith('/comments')) {
        row = { ...row, rev: 4, comments: [{ id: 'c', display_name: 'Gipsz Jakab', avatar: null, body: 'Megjegyzés', created_at: new Date().toISOString() }] };
        return { body: row };
      }
      if (method === 'PATCH') { row = { ...row, ...(body as { set: object }).set, rev: 5 }; return { body: row }; }
      return detailRoute(url, row);
    });
    const { container } = await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    await click(container.querySelector('button[aria-label="Határidő"]')!);
    await type('input[aria-label="Határidő napja"]', '2026-12-31');
    const dateInput = document.querySelector('input[aria-label="Határidő napja"]');
    await type('textarea[aria-label="Új komment"]', 'Megjegyzés');
    await key('textarea[aria-label="Új komment"]', { ctrlKey: true });
    expect(calls.filter(c => c.method === 'PATCH')).toHaveLength(0);
    expect(container.textContent).toContain('Megjegyzés');
    expect(document.querySelector('input[aria-label="Határidő napja"]')).toBe(dateInput);
    expect((dateInput as HTMLInputElement).value).toBe('2026-12-31');
    await click(container.querySelector('button[aria-label="Határidő"]')!);
    expect(calls.find(c => c.method === 'PATCH')?.body).toEqual({ expected_rev: 4, set: { due_date: '2026-12-31' } });
  });
  it('keeps an unsaved description through comment reload and saves on blur', async () => {
    let row = { ...task };
    const calls = stubApi((url, method, body) => {
      if (method === 'POST') { row = { ...row, rev: 4 }; return { body: row }; }
      if (method === 'PATCH') return { body: { ...row, ...(body as { set: object }).set, rev: 5 } };
      return detailRoute(url, row);
    });
    const { container } = await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    await click(container.querySelector('.todo-note')!);
    await type('textarea[aria-label="Jegyzet…"]', 'Még szerkesztem');
    await type('textarea[aria-label="Új komment"]', 'Közben egy komment');
    await key('textarea[aria-label="Új komment"]', { metaKey: true });
    expect((container.querySelector('textarea[aria-label="Jegyzet…"]') as HTMLTextAreaElement).value).toBe('Még szerkesztem');
    expect(calls.filter(c => c.method === 'PATCH')).toHaveLength(0);
    container.querySelector('textarea[aria-label="Jegyzet…"]')!.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    await tick(100);
    expect(calls.find(c => c.method === 'PATCH')?.body).toEqual({ expected_rev: 4, set: { description: 'Még szerkesztem' } });
  });
  it('marks agents, resolves known mentions and keeps old comment payloads readable', async () => {
    const comments = [
      { id: 'a', display_name: 'Bot', avatar: null, kind: 'agent' as const, handle: 'bot', body: '@owner @unknown lépés email@owner é@owner +@owner', created_at: new Date().toISOString() },
      { id: 'b', display_name: 'Régi név', avatar: null, body: 'Régi komment', created_at: new Date().toISOString() },
    ];
    stubApi(url => detailRoute(url, { ...task, comments }));
    const { container } = await show('/feladatok/one', [['feladatok/:id', <TaskPage />]]);
    expect(container.querySelectorAll('[aria-label="Ágens"]')).toHaveLength(1);
    expect(container.querySelector('.todo-mention-own')?.textContent).toBe(`@${principal.handle}`);
    expect(container.querySelectorAll('.todo-mention')).toHaveLength(1);
    expect(container.textContent).toContain('@unknown');
    expect(container.textContent).toContain('Régi komment');
  });
});
