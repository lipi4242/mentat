import { describe, expect, it } from 'vitest';
import type { AdminPluginRoute } from './plugin';

// Compile-time contract: AdminApp renders plugin routes as a bare
// `<Route path element />`, so anything else react-router's RouteObject
// allows (children / index / Component) must be rejected here rather than
// silently never rendering. `npm run typecheck` is what enforces this.
describe('AdminPluginRoute', () => {
  it('rejects route shapes AdminApp cannot render', () => {
    const ok: AdminPluginRoute = { path: 'beszerzes', element: null };

    // @ts-expect-error nested children are dropped by AdminApp's renderer
    const nested: AdminPluginRoute = { path: 'a', element: null, children: [] };

    // @ts-expect-error a pathless layout route would collide with the shell
    const pathless: AdminPluginRoute = { element: null };

    expect([ok, nested, pathless]).toHaveLength(3);
  });
});
