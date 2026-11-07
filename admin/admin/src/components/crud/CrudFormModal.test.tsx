import { afterEach, describe, expect, it, vi } from 'vitest';
import { Refine } from '@refinedev/core';
import routerBindings from '@refinedev/react-router-v6';
import { MemoryRouter } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import { render, tick } from '../../test-render';
import { CrudFormModal } from './CrudFormModal';
import { dataProvider } from '../../dataProvider';
import type { FieldSpec } from './values';

const FIELDS: readonly FieldSpec[] = [
  { name: 'price', label: 'Ár', type: 'number' },
  { name: 'in_stock', label: 'Raktáron', type: 'checkbox' },
];

afterEach(() => vi.unstubAllGlobals());

async function editOffer(record: Record<string, unknown>) {
  const bodies: Array<{ method: string; body: string }> = [];
  vi.stubGlobal('fetch', vi.fn(async (_url: unknown, init: any) => {
    if (init?.body) bodies.push({ method: init.method, body: init.body });
    return new Response('{"id":"o1"}', { status: 200, headers: { 'content-type': 'application/json' } });
  }));
  const r = await render(
    <ConfigProvider>
      <AntApp>
        <MemoryRouter>
          <Refine dataProvider={dataProvider} routerProvider={routerBindings} options={{ disableTelemetry: true }}>
            <CrudFormModal resource="offers" title="ár" fields={FIELDS} target={{ mode: 'edit', record }} onClose={() => {}} />
          </Refine>
        </MemoryRouter>
      </AntApp>
    </ConfigProvider>,
  );
  await tick(50);
  return { ...r, bodies };
}

const save = async () => {
  const ok = [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('Mentés'))!;
  ok.click();
  await tick(200);
};

describe('editing a row with a checkbox', () => {
  // What the box shows and what the PATCH says have to agree. They did not:
  // the box rendered ticked and the body cleared the column.
  it('does not clear an untouched checkbox', async () => {
    const { bodies, unmount } = await editOffer({ id: 'o1', price: 100, in_stock: 1 });
    expect((document.querySelector('input[type=checkbox]') as HTMLInputElement).checked).toBe(true);
    await save();
    expect(bodies[0].method).toBe('PATCH');
    expect(JSON.parse(bodies[0].body)).toEqual({ price: 100, in_stock: true });
    unmount();
  });

  it('still sends an explicit false when the box is unticked', async () => {
    const { bodies, unmount } = await editOffer({ id: 'o1', price: 100, in_stock: 1 });
    (document.querySelector('input[type=checkbox]') as HTMLInputElement).click();
    await tick(20);
    await save();
    expect(JSON.parse(bodies[0].body)).toEqual({ price: 100, in_stock: false });
    unmount();
  });
});
