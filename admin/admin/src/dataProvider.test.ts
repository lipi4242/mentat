import { afterEach, describe, expect, it, vi } from 'vitest';
import { dataProvider } from './dataProvider';

const json = (body: string, init: ResponseInit = {}) =>
  vi.fn(async () => new Response(body, { status: 200, headers: { 'content-type': 'application/json' }, ...init }));

afterEach(() => vi.unstubAllGlobals());

describe('dataProvider.getList', () => {
  it('returns rows and a total', async () => {
    vi.stubGlobal('fetch', json('[{"id":1},{"id":2}]'));
    await expect(dataProvider.getList({ resource: 'needs' } as any)).resolves.toEqual({
      data: [{ id: 1 }, { id: 2 }],
      total: 2,
    });
  });

  // An empty body used to blow up as "Cannot read properties of null
  // (reading 'length')" — an internal TypeError shown to the user.
  it('treats an empty body as zero rows', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 200 })));
    await expect(dataProvider.getList({ resource: 'needs' } as any)).resolves.toEqual({ data: [], total: 0 });
  });

  it('treats a 204 as zero rows', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));
    await expect(dataProvider.getList({ resource: 'needs' } as any)).resolves.toEqual({ data: [], total: 0 });
  });

  // A misrouted /api/* falls through to the SPA and returns index.html at 200.
  it('surfaces an HTML 200 as a readable ApiError, not a raw SyntaxError', async () => {
    vi.stubGlobal('fetch', json('<!doctype html><html></html>', { headers: { 'content-type': 'text/html' } }));
    const err = (await dataProvider.getList({ resource: 'needs' } as any).catch((e) => e)) as Error;
    expect(err.name).toBe('ApiError');
    expect(err.message).toMatch(/váratlan választ/);
  });

  it('rejects a non-array list body instead of rendering an empty table', async () => {
    vi.stubGlobal('fetch', json('{"items":[]}'));
    const err = (await dataProvider.getList({ resource: 'needs' } as any).catch((e) => e)) as Error;
    expect(err.name).toBe('ApiError');
  });
});

describe('dataProvider writes', () => {
  it('update sends PATCH with a JSON body to the id path', async () => {
    const f = json('{"id":"a b"}');
    vi.stubGlobal('fetch', f);
    await dataProvider.update({ resource: 'needs', id: 'a b', variables: { q: 1 } } as any);
    const [url, init] = f.mock.calls[0] as any;
    expect(url).toBe('/api/needs/a%20b');
    expect(init.method).toBe('PATCH');
    expect(init.body).toBe('{"q":1}');
    expect(init.credentials).toBe('include');
  });

  it('create POSTs to the collection', async () => {
    const f = json('{"id":1}');
    vi.stubGlobal('fetch', f);
    await dataProvider.create({ resource: 'needs', variables: { q: 1 } } as any);
    expect((f.mock.calls[0] as any)[0]).toBe('/api/needs');
    expect((f.mock.calls[0] as any)[1].method).toBe('POST');
  });

  it('deleteOne rejects — needs are archived', async () => {
    await expect(dataProvider.deleteOne!({ resource: 'needs', id: 1 } as any)).rejects.toThrow(/archived/);
  });
});
