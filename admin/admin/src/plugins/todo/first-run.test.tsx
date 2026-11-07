import { describe, expect, it, vi } from 'vitest';
import { authClient } from '../../lib/authClient';
import { TasksPage } from './TasksPage';
import { TaskPage } from './TaskPage';
import { show, stubApi, click, button, detailRoute } from './testkit';
vi.mock('../../lib/authClient', () => ({ authClient: { getSession: vi.fn(async () => ({ data: { user: { email: 'Ár.Víz+1@example.com' } } })) } }));
describe('first run', () => {
  it.each(['list', 'detail'])('bootstraps the %s with one click and reloads in place', async page => {
    let created = false;
    const calls = stubApi((url, method) => {
      if (method === 'POST') { created = true; return { status: 201, body: {} }; }
      return created ? detailRoute(url) : { status: 403, body: {} };
    });
    const { container } = await show(page === 'list' ? '/feladatok' : '/feladatok/one',
      [['feladatok', <TasksPage />], ['feladatok/:id', <TaskPage />]]);
    expect(container.textContent).toContain('Még nem ismerlek.');
    expect(container.textContent).not.toContain('Ehhez nincs jogosultságod.');
    await click(button('Létrehozlak')[0]);
    expect(calls.find(c => c.method === 'POST')).toMatchObject({ url: '/api/todo/v1/principals',
      body: { kind: 'human', auth_email: 'ár.víz+1@example.com', display_name: 'ár.víz+1', handle: 'ar_viz_1', idem_key: expect.any(String) } });
    expect(container.textContent).toContain('Reggeli rutin');
    expect(container.textContent).not.toContain('Még nem ismerlek.');
  });
  it('retries bootstrap with the same idempotency key', async () => {
    const calls = stubApi((_url, method) => ({ status: method === 'POST' ? 500 : 403, body: {} }));
    await show('/feladatok', [['feladatok', <TasksPage />]]);
    await click(button('Létrehozlak')[0]); await click(button('Létrehozlak')[0]);
    const writes = calls.filter(c => c.method === 'POST');
    expect(writes).toHaveLength(2); expect(writes[1].body).toEqual(writes[0].body);
  });
  it('does not create a principal without a session email', async () => {
    vi.mocked(authClient.getSession).mockResolvedValueOnce({ data: null, error: null } as never);
    const calls = stubApi(() => ({ status: 403, body: {} }));
    await show('/feladatok', [['feladatok', <TasksPage />]]);
    await click(button('Létrehozlak')[0]);
    expect(document.body.textContent).toContain('Jelentkezz be újra.');
    expect(calls.some(c => c.method === 'POST')).toBe(false);
  });
});
