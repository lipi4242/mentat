import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App as AntApp, ConfigProvider } from 'antd';
import { render, act, tick } from '../test-render';

// better-auth's client binds `fetch` when the module is first evaluated, so
// the stub has to be in place BEFORE Login (and with it authClient) loads.
beforeEach(() => vi.resetModules());
afterEach(() => vi.unstubAllGlobals());

function typeInto(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function mountLogin(onFetch: (url: string) => Promise<Response>) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: any) => {
    calls.push(String(url));
    return onFetch(String(url));
  }));
  const { Login } = await import('./Login');
  const r = await render(
    <ConfigProvider>
      <AntApp>
        <Login />
      </AntApp>
    </ConfigProvider>,
  );
  return { ...r, calls };
}

const slowOk = () =>
  new Promise<Response>((resolve) =>
    setTimeout(() => resolve(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })), 200),
  );

describe('Login', () => {
  // antd's `loading` button only swallows its own onClick — Enter in the input
  // still fires a native submit. A second send invalidates the first OTP, so
  // the code already in the user's inbox stops working.
  it('sends only one OTP when the form is submitted twice in flight', async () => {
    const { container, calls, unmount } = await mountLogin(slowOk);
    await act(async () => typeInto(container.querySelector('input')!, 'owner@example.com'));

    // Two presses while the first request is still in flight — the realistic
    // impatient double-click / double-Enter.
    const form = container.querySelector('form')!;
    const press = () => {
      (container.querySelector('button') as HTMLButtonElement).click();
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    };
    await act(async () => {
      press();
      await new Promise((r) => setTimeout(r, 80));
    });
    await act(async () => {
      press();
      await new Promise((r) => setTimeout(r, 300));
    });

    expect(calls.filter((u) => u.includes('send-verification-otp'))).toHaveLength(1);
    unmount();
  });

  it('never renders the address into an error message', async () => {
    const { container, unmount } = await mountLogin(async () =>
      new Response(JSON.stringify({ message: 'Rate limited' }), {
        status: 429, headers: { 'content-type': 'application/json' },
      }),
    );
    await act(async () => typeInto(container.querySelector('input')!, 'titkos@example.com'));
    await act(async () => {
      (container.querySelector('button') as HTMLButtonElement).click();
    });
    await tick(50);
    const alerts = [...document.querySelectorAll('.ant-message')].map((e) => e.textContent ?? '').join(' ');
    expect(alerts).not.toContain('titkos@example.com');
    unmount();
  });
});
