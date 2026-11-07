import { afterEach, describe, expect, it, vi } from 'vitest';
import { App as AntApp, ConfigProvider } from 'antd';
import { render, tick } from '../../test-render';
import { TokensPage } from './TokensPage';

afterEach(() => vi.unstubAllGlobals());

const SECRET = 'mentat_only-shown-once';
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });

async function page(rows: unknown[]) {
  const calls: Array<{ url: string; method: string; body?: string }> = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: any = {}) => {
    calls.push({ url, method: init.method ?? 'GET', body: init.body });
    if (url.endsWith('/api/tokens') && init.method === 'POST') {
      return json({ id: 't2', label: 'agent1', scopes: 'cases:write', expires_at: '2027-01-13 00:00:00', token: SECRET });
    }
    if (url.includes('/revoke')) return json({ id: 't1', active: 0 });
    return json(rows);
  }));
  const r = await render(<ConfigProvider><AntApp><TokensPage /></AntApp></ConfigProvider>);
  await tick(50);
  return { ...r, calls };
}

const button = (text: string) => [...document.querySelectorAll('button')].find((b) => b.textContent?.includes(text))!;

describe('TokensPage', () => {
  it('lists tokens and revokes an active one after confirmation', async () => {
    const { container, calls, unmount } = await page([
      { id: 't1', label: 'agent1', scopes: 'cases:write', active: 1, expires_at: '2027-01-01 00:00:00', created_at: 'x', last_used_at: null },
    ]);
    expect(container.textContent).toContain('agent1');
    button('Visszavonás').click();
    await tick(50);
    [...document.querySelectorAll('.ant-popconfirm button')].find((b) => b.textContent?.includes('Visszavonás'))!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await tick(100);
    expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/tokens/t1/revoke'))).toBe(true);
    unmount();
  });

  it('mints a token and shows it once', async () => {
    const { calls, unmount } = await page([]);
    button('Új token').click();
    await tick(50);
    const label = document.querySelector('input#label') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    setter.call(label, 'agent1');
    label.dispatchEvent(new Event('input', { bubbles: true }));
    await tick(20);
    button('Kiadás').click();
    await tick(200);
    const post = calls.find((c) => c.method === 'POST');
    expect(JSON.parse(post!.body!)).toEqual({ label: 'agent1', scopes: 'cases:write', days: 90 });
    expect(document.querySelector('[data-testid=minted-token]')?.textContent).toContain(SECRET);
    button('Elmentettem').click();
    await tick(300);
    expect(document.body.textContent).not.toContain(SECRET);
    unmount();
  });
});
