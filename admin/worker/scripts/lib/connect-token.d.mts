type Query = (sqls: string[]) => Promise<Record<string, any>[][]>;
type Minted = { id: string; label: string; scopes: string; expires_at: string; url: string; tokenEnv: string; envFile: string };
export function pluginsFor(doc: any, asked: string[] | undefined): string[];
export function neededScopes(plugins: string[]): string;
export function bindToken(opts: {
  query: Query;
  repo: string;
  origin?: string;
  tokenEnv: string;
  asked?: string[];
  scope?: string;
  handle?: string;
  works: (token: string) => Promise<boolean>;
  connectFn: (scopes: string, plugins: string[]) => Promise<Minted>;
}): Promise<{ kept?: { id: string; label: string; scopes: string }; minted?: Minted; revoked: string[]; handle?: string }>;
