import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, tick } from './test-render';

// A signed-in shell with no way out is a dead end: Refine only renders the
// sider's Logout item when an authProvider with `logout` is wired in.
afterEach(() => vi.unstubAllGlobals());

describe('sign-out', () => {
  it('the shell offers a logout that hits better-auth', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: any) => {
      calls.push(String(url));
      return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } });
    }));
    window.history.pushState({}, '', '/ugyek');
    const { AdminApp } = await import('./core/AdminApp');
    const { container, unmount } = await render(<AdminApp />);

    const logout = container.querySelector('[data-menu-id$="logout"]') as HTMLElement | null;
    expect(logout, 'no logout item in the shell').not.toBeNull();
    // The rest of the UI is Hungarian; Refine's own chrome must be too.
    expect(logout!.textContent).toBe('Kijelentkezés');

    logout!.click();
    await tick(50);
    expect(calls.some((u) => u.includes('sign-out'))).toBe(true);
    unmount();
  });
});

// The i18nProvider returns undefined for anything it does not override, so
// Refine's own fallback chain still supplies every other label. If that
// contract broke, chrome would render blank or as a raw "buttons.foo" key.
describe('i18nProvider fallbacks', () => {
  it('leaves untranslated Refine chrome intact', async () => {
    const { i18nProvider } = await import('./i18nProvider');
    const t = (key: string, options?: any, defaultMessage?: string) =>
      i18nProvider.translate(key, options, defaultMessage) ??
      defaultMessage ??
      (typeof options === 'string' && defaultMessage === undefined ? options : key);

    expect(t('buttons.logout', 'Logout')).toBe('Kijelentkezés');
    expect(t('buttons.save', 'Save')).toBe('Save');
    expect(t('pages.error.404', {}, 'Sorry, the page you visited does not exist.')).toBe(
      'Sorry, the page you visited does not exist.',
    );
    expect(t('unknown.key')).toBe('unknown.key');
  });

  it('renders no blank or raw-key labels anywhere in the shell', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', {
      status: 200, headers: { 'content-type': 'application/json' },
    })));
    window.history.pushState({}, '', '/ugyek');
    const { AdminApp } = await import('./core/AdminApp');
    const { container, unmount } = await render(<AdminApp />);

    const labels = [...container.querySelectorAll('[data-menu-id]')].map((e) => e.textContent ?? '');
    expect(labels.length).toBeGreaterThan(0);
    for (const label of labels) {
      expect(label.trim(), 'blank menu label').not.toBe('');
      expect(label, 'untranslated i18n key leaked into the UI').not.toMatch(/^[a-z]+\.[a-z]/);
    }
    expect(labels).toContain('Ügyek');
    unmount();
  });
});
