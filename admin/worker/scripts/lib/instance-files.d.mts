export const INSTANCE_BRANCH: string;
export function writeInstanceFile(path: string, body: string): void;
export function commitInstance(opts: {
  root: string;
  files: string[];
  message: string;
  env?: NodeJS.ProcessEnv;
}): { committed: boolean; branch?: string; sha?: string; reason?: string };
