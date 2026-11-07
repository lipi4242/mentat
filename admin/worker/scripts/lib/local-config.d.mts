export const PUBLISHED_DEV_SECRET: string;
export const DEFAULT_EMAIL: string;
export function localConfigPath(root: string): string;
export function renderLocalWrangler(base: string, opts: { root: string }): string;
export function wranglerDevArgs(opts: { root: string; port: number }): string[];
export function parseDevVars(text: string): Record<string, string>;
export function updateDevVars(
  text: string,
  opts: { port: number; email?: string; secret: string; fallback?: string },
): { text: string; email: string };
export function gitEmail(repo: string): string;
