import { describe, it, expect } from 'vitest';
import app from '../src/index';
import { makeEnv } from './helpers';

describe('health', () => {
  it('reports the service name', async () => {
    const res = await app.request('/api/health', {}, makeEnv());
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, service: 'mentat-admin' });
  });
});
