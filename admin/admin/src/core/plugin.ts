import type { ResourceProps } from '@refinedev/core';
import type { ReactNode } from 'react';

/**
 * One plugin screen. Deliberately NOT react-router's `RouteObject`: AdminApp
 * renders these as `<Route path element />` inside its own layout route, so
 * `children` / `index` / `Component` / `loader` would be accepted by the type
 * and then silently dropped — the URL would fall through to the catch-all and
 * the screen would never render. Narrow type ⇒ the compiler catches it.
 */
export interface AdminPluginRoute {
  path: string;
  element: ReactNode;
}

/**
 * The frontend half of a plugin. Mirrors the worker's `AdminPlugin` shape
 * (worker/src/core/plugin.ts) but stays a separate type — the SPA bundle
 * must not import worker code.
 */
export interface AdminPluginUI {
  id: string;
  title: string;
  icon: ReactNode;
  resources: ResourceProps[];
  routes: AdminPluginRoute[];
}
