export function toolArgv(name: string, env?: NodeJS.ProcessEnv): string[];
export function runTool(
  name: string,
  args: string[],
  opts?: { input?: string; cwd?: string; env?: NodeJS.ProcessEnv },
): { status: number; stdout: string; stderr: string };
