import { describe, expect, it } from 'vitest';
import { UI_PLUGINS } from '../instance';
import type { AdminPluginUI } from './plugin';

/**
 * Runtime half of the AdminPluginRoute contract. The type stops a nested
 * route at compile time; this stops the mistakes it cannot see:
 *
 *  - a `show` (or `list`) path with no matching route, which renders the
 *    catch-all redirect instead of the screen;
 *  - a route param named anything but `:id`. Refine resolves the record id
 *    by pairing the resource's `show` pattern with the rendered route, so a
 *    `:needId` leaves `useParsed().id` undefined and every useOne() on the
 *    detail page fetches nothing, silently;
 *  - a plugin that declares no routes at all (a stub exporting `routes: []`
 *    still typechecks).
 *
 * The rules run against the real plugin list AND a synthetic pair: the core
 * ships with no plugin, so the real list alone would pass vacuously.
 */
function routeProblems(plugins: AdminPluginUI[]): string[] {
  const problems: string[] = [];
  for (const p of plugins) {
    const paths = new Set(p.routes.map((r) => r.path));
    if (!paths.size) problems.push(`${p.id}: no routes`);
    for (const r of p.resources) {
      for (const target of [r.list, r.show]) {
        if (typeof target !== 'string') continue;
        if (!paths.has(target.replace(/^\//, ''))) problems.push(`${p.id}/${r.name}: no route for ${target}`);
      }
    }
    for (const path of paths) {
      for (const segment of path.split('/')) {
        if (segment.startsWith(':') && segment !== ':id') problems.push(`${p.id}: param ${segment} in ${path}`);
      }
    }
  }
  return problems;
}

const plugin = (over: Partial<AdminPluginUI>): AdminPluginUI => ({
  id: 'demo',
  title: 'Demo',
  icon: null,
  resources: [{ name: 'things', list: '/demo', show: '/demo/:id' }],
  routes: [
    { path: 'demo', element: null },
    { path: 'demo/:id', element: null },
  ],
  ...over,
});

describe('plugin route wiring', () => {
  it('holds for every compiled-in plugin', () => {
    expect(routeProblems(UI_PLUGINS)).toEqual([]);
  });

  it('accepts a correctly wired plugin', () => {
    expect(routeProblems([plugin({})])).toEqual([]);
  });

  it('catches a missing route, a non-id param and an empty route list', () => {
    expect(routeProblems([plugin({ routes: [{ path: 'demo', element: null }] })])).toEqual([
      'demo/things: no route for /demo/:id',
    ]);
    expect(
      routeProblems([
        plugin({
          resources: [{ name: 'things', list: '/demo', show: '/demo/:thingId' }],
          routes: [
            { path: 'demo', element: null },
            { path: 'demo/:thingId', element: null },
          ],
        }),
      ]),
    ).toEqual(['demo: param :thingId in demo/:thingId']);
    expect(routeProblems([plugin({ resources: [], routes: [] })])).toEqual(['demo: no routes']);
  });
});
