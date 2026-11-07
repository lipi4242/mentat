import type { QueryMany } from './dump.mjs';
import type { Minted, MintRequest } from './mint.mjs';
export function remoteScript(tokenFile: string): string;
export function parseRemote(stdout: string): { id: string; hash: string; file: string };
export function sshArgs(target: string, remoteNode?: string): string[];
export function mintOn(
  queryMany: QueryMany,
  request: MintRequest,
  opts: { on: string; tokenFile: string; remoteNode?: string; env?: NodeJS.ProcessEnv; now?: Date },
): Promise<Omit<Minted, 'token'> & { file: string }>;
