import type { Run } from './local-admin.mjs';
export const LABEL: string;
export function plistPath(home: string): string;
export function logPath(home: string): string;
export function renderPlist(opts: { workerDir: string; nodeBin: string; port: number; log: string }): string;
export function nodeOfPlist(text: string | null | undefined): string | null;
export function portOfPlist(text: string | null | undefined): number | null;
export function installLaunchAgent(opts: { home: string; uid?: number; workerDir: string; nodeBin: string; port: number; run: Run }): {
  installed: true;
  unitPath: string;
  note: string;
};
export function uninstallLaunchAgent(opts: { home: string; uid?: number; run: Run }): { removed: string[] };
export type PrintState = { state: string; pid: number | null; runs: number | null; lastExit: string | null };
export function parsePrint(out: string): PrintState;
export function launchdState(opts: { home: string; uid?: number; run: Run; exists?: (p: string) => boolean }):
  | { installed: false }
  | ({ installed: true; node: string | null; nodeOk: boolean; port: number | null } & PrintState);
