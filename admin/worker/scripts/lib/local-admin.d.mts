export type Run = (cmd: string, args: string[]) => { status: number | null; stdout: string };
export const UNIT: string;
export const defaultRun: Run;
export function localPort(url: string): number;
export function linkNode(opts: { home: string; nodeBin: string }): { linked: string[]; skipped: string[] };
export function renderUnit(opts: { workerDir: string; nodeBin: string; port: number }): string;
export function installService(opts: {
  home: string;
  user: string;
  workerDir: string;
  nodeBin: string;
  port: number;
  run?: Run;
}): { installed: boolean; reason?: string; unitPath?: string; linger?: boolean; hint?: string };
export function waitHealthy(origin: string, opts?: { timeoutMs?: number; fetchFn?: typeof fetch }): Promise<boolean>;
