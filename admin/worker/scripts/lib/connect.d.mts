import type { Minted } from './mint.mjs';
export function gitIgnores(repo: string, rel: string): boolean;
export function checkUrl(url: string): string;
export function upsertEnv(path: string, key: string, value: string): void;
export function connect(opts: {
  repo: string;
  url: string;
  tokenEnv?: string;
  agent?: string;
  scopes?: string;
  days?: number | string;
  plugins?: string[];
  mintFn: (req: { label: unknown; scopes: unknown; days?: unknown }) => Promise<Minted>;
  ignores?: (repo: string, rel: string) => boolean;
}): Promise<Omit<Minted, 'token'> & { url: string; tokenEnv: string; envFile: string }>;
