export function cliState(repo: string): 'current' | 'missing' | 'stale';
export function installCli(repo: string): 'installed' | 'updated' | 'current';
export function blockState(repo: string, opts: { origin: string; dir: string; local: boolean; cases?: boolean }): { p: string; text: string; next: string; state: 'current' | 'missing' | 'stale' };
export function writeBlock(repo: string, opts: { origin: string; dir: string; local: boolean; cases?: boolean }): 'added' | 'updated' | 'current';
export function tokenWorks(origin: string, token: string): Promise<boolean>;
export function envValue(repo: string, key: string): string;
export function migrateBrain(repo: string): number;
