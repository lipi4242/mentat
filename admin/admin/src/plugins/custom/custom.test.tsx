// A whole entity declared in config/models.json appears here with its list
// and form, drawn from GET /api/meta alone.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Refine } from '@refinedev/core';
import routerBindings from '@refinedev/react-router-v6';
import { App as AntApp, ConfigProvider } from 'antd';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, tick } from '../../test-render';
import { dataProvider } from '../../dataProvider';
import { stubApi, button, click, type } from '../cases/testkit';
import { DataPage } from './DataPage';

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
});

const META = {
  fields: {},
  entities: [
    {
      name: 'ugyfelek', label: 'Ügyfelek', path: '/api/ugyfelek',
      fields: [
        { name: 'nev', label: 'Név', type: 'text', required: true },
        { name: 'email', label: 'E-mail', type: 'email' },
      ],
    },
  ],
};

async function open(path: string, meta: unknown) {
  const calls = stubApi((url, method) =>
    url.endsWith('/api/meta') ? { body: meta } : method === 'POST' ? { body: { id: 'u2' } } : { body: [{ id: 'u1', nev: 'Kertész Anna', email: 'anna@example.com' }] },
  );
  const r = await render(
    <ConfigProvider>
      <AntApp>
        <MemoryRouter initialEntries={[path]}>
          <Refine dataProvider={dataProvider} routerProvider={routerBindings} options={{ disableTelemetry: true }}>
            <Routes>
              <Route path="adatok" element={<DataPage />} />
              <Route path="adatok/:id" element={<DataPage />} />
            </Routes>
          </Refine>
        </MemoryRouter>
      </AntApp>
    </ConfigProvider>,
  );
  await tick(150);
  return { ...r, calls };
}

describe('Saját adatok', () => {
  it('lists a declared entity with its own columns, and creates a row through its API', async () => {
    const { container, calls } = await open('/adatok', META);
    expect([...container.querySelectorAll('th')].map((t) => t.textContent)).toEqual(expect.arrayContaining(['Név', 'E-mail']));
    expect(container.querySelector('tbody tr')!.textContent).toContain('Kertész Anna');
    await click(button('Új ügyfelek')[0]);
    await type('input#nev', 'Kovács Béla');
    await click(button('Mentés')[0]);
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.url).toMatch(/\/api\/ugyfelek$/);
    expect(post.body).toEqual({ nev: 'Kovács Béla' });
  });

  it('says what to ask for when nothing is declared yet', async () => {
    const { container } = await open('/adatok', { fields: {}, entities: [] });
    expect(container.textContent).toContain('Még nincs saját adatmodell');
  });
});
