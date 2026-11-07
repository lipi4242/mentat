import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from '../test-render';

// Probe the detail page from the inside: Refine must be able to resolve the
// case id from the URL, or every useShow()/useOne() in Task 10 fetches
// nothing. The route param name has to match the resource's `show` pattern.
const parsed: Array<{ id?: unknown; resource?: string; action?: string }> = [];
vi.mock('../plugins/cases/CaseShowPage', async () => {
  const { useParsed } = await import('@refinedev/core');
  return {
    CaseShowPage: () => {
      const p = useParsed();
      parsed.push({ id: p.id, resource: p.resource?.name, action: p.action });
      return <div>detail</div>;
    },
  };
});

afterEach(() => vi.unstubAllGlobals());

describe('AdminApp routing', () => {
  it('hands Refine the case id on the show route', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', {
      status: 200, headers: { 'content-type': 'application/json' },
    })));
    window.history.pushState({}, '', '/ugyek/42');
    const { AdminApp } = await import('./AdminApp');
    const { unmount } = await render(<AdminApp />);
    expect(parsed.at(-1)).toEqual({ id: '42', resource: 'cases', action: 'show' });
    unmount();
  });
});
