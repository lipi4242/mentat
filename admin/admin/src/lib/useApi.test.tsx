import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, tick } from '../test-render';
import { useApi } from './useApi';

const seen: Array<{ data: unknown; error: string | null; loading: boolean }> = [];

function Probe({ path }: { path: string | null }) {
  const s = useApi<{ ok: number }>(path);
  seen.push({ data: s.data, error: s.error?.message ?? null, loading: s.loading });
  return <button onClick={s.reload}>reload</button>;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

afterEach(() => {
  seen.length = 0;
  vi.unstubAllGlobals();
});

describe('useApi', () => {
  it('fetches and settles', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ok: 1 })));
    const { unmount } = await render(<Probe path="/api/needs/1/coverage" />);
    await tick();
    expect(seen.at(-1)).toEqual({ data: { ok: 1 }, error: null, loading: false });
    unmount();
  });

  it('surfaces the Hungarian message for a failed status', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ error: 'not found' }, 404)));
    const { unmount } = await render(<Probe path="/api/needs/9/coverage" />);
    await tick();
    expect(seen.at(-1)?.data).toBeNull();
    expect(seen.at(-1)?.error).toMatch(/Nincs ilyen tétel/);
    unmount();
  });

  it('stays idle and issues no request for a null path', async () => {
    const fetchSpy = vi.fn(async () => json({ ok: 1 }));
    vi.stubGlobal('fetch', fetchSpy);
    const { unmount } = await render(<Probe path={null} />);
    await tick();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(seen.at(-1)).toEqual({ data: null, error: null, loading: false });
    unmount();
  });

  it('re-requests on reload', async () => {
    const fetchSpy = vi.fn(async () => json({ ok: 1 }));
    vi.stubGlobal('fetch', fetchSpy);
    const { container, unmount } = await render(<Probe path="/api/needs/1/coverage" />);
    await tick();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    container.querySelector('button')!.click();
    await tick();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    unmount();
  });
});
