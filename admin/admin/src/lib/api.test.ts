import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpMessage, ApiError, apiGet, apiGetWithTotal, apiSend } from './api';

describe('httpMessage', () => {
  it('maps known statuses to Hungarian messages', () => {
    expect(httpMessage(400)).toMatch(/Érvénytelen/);
    expect(httpMessage(401)).toMatch(/belépésed/);
    expect(httpMessage(403)).toMatch(/jogosultságod/);
    expect(httpMessage(404)).toMatch(/Nincs ilyen/);
    expect(httpMessage(409)).toMatch(/Ütközés/);
    expect(httpMessage(429)).toMatch(/Túl sok/);
    expect(httpMessage(500)).toMatch(/Rendszerhiba/);
  });

  it('falls back for unknown statuses', () => {
    expect(httpMessage(418)).toBe('Váratlan hiba (418).');
  });
});

describe('ApiError', () => {
  it('carries the status code and a matching message', () => {
    const err = new ApiError(409);
    expect(err.statusCode).toBe(409);
    expect(err.message).toMatch(/Ütközés/);
  });
});

afterEach(() => vi.unstubAllGlobals());

describe('body parsing', () => {
  it('apiGet turns a non-JSON 200 into a readable ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<!doctype html>', {
      status: 200, headers: { 'content-type': 'text/html' },
    })));
    const err = (await apiGet('/api/needs').catch((e) => e)) as ApiError;
    expect(err.name).toBe('ApiError');
    expect(err.message).toMatch(/váratlan választ/);
  });

  it('apiSend tolerates an empty 200 body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 200 })));
    await expect(apiSend('POST', '/api/needs', { a: 1 })).resolves.toBeNull();
  });

  it('a 422 carries the worker\'s own reason, and the body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"error":"anchor_at is required"}', { status: 422 })));
    const err = (await apiSend('PUT', '/api/cases/x', {}).catch((e) => e)) as ApiError;
    expect(err.statusCode).toBe(422);
    expect(err.message).toMatch(/nem fogadta el.*anchor_at is required/);
    expect(err.body).toEqual({ error: 'anchor_at is required' });
  });

  it('a non-ok status still wins over the body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>oops</html>', { status: 403 })));
    const err = (await apiGet('/api/needs').catch((e) => e)) as ApiError;
    expect(err.statusCode).toBe(403);
    expect(err.message).toMatch(/jogosultságod/);
  });
});

describe('apiGetWithTotal', () => {
  const listWith = (headers: Record<string, string>) =>
    vi.fn(async () => new Response('[{"id":1}]', { status: 200, headers: { 'content-type': 'application/json', ...headers } }));

  it('reads a numeric X-Total-Count', async () => {
    vi.stubGlobal('fetch', listWith({ 'X-Total-Count': '42' }));
    expect((await apiGetWithTotal('/api/needs')).total).toBe(42);
  });

  // A NaN total makes antd render no pagination at all.
  it('falls back to the row count for a non-numeric header', async () => {
    vi.stubGlobal('fetch', listWith({ 'X-Total-Count': 'abc' }));
    const { total } = await apiGetWithTotal('/api/needs');
    expect(Number.isNaN(total)).toBe(false);
    expect(total).toBe(1);
  });

  it('falls back to the row count when the header is absent', async () => {
    vi.stubGlobal('fetch', listWith({}));
    expect((await apiGetWithTotal('/api/needs')).total).toBe(1);
  });
});
