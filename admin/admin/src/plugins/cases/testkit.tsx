// Test harness for the cases screens: a fetch stub that records every call
// and answers by URL, and a router around the page under test.
import { vi } from 'vitest';
import type { ReactElement } from 'react';
import { App as AntApp, ConfigProvider } from 'antd';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, tick } from '../../test-render';

export type Call = { url: string; method: string; body: unknown };
type Answer = { status?: number; body: unknown };

export function stubApi(route: (url: string, method: string, body: unknown) => Answer) {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET';
      const body = init.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });
      const a = route(url, method, body);
      return new Response(JSON.stringify(a.body), { status: a.status ?? 200, headers: { 'content-type': 'application/json' } });
    }),
  );
  return calls;
}

export async function show(path: string, routes: Array<[string, ReactElement]>) {
  const r = await render(
    <ConfigProvider>
      <AntApp>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            {routes.map(([p, el]) => (
              <Route key={p} path={p} element={el} />
            ))}
          </Routes>
        </MemoryRouter>
      </AntApp>
    </ConfigProvider>,
  );
  await tick(50);
  return r;
}

export const button = (text: string) =>
  [...document.querySelectorAll('button')].filter((b) => b.textContent?.includes(text));

export async function click(el: Element | undefined) {
  if (!el) throw new Error('nothing to click');
  el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  await tick(150);
}

/** Type into an antd input the way React notices (native setter + input event). */
export async function type(selector: string, value: string) {
  const el = document.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement | null;
  if (!el) throw new Error(`no input ${selector}`);
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
  await tick(20);
}
