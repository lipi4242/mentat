// External programs the scripts run, in one place, each overridable by an
// environment variable. The override exists for the tests: a fake wrangler
// or ssh on a temp path, so no test ever reaches Cloudflare or a real host.
//
//   wrangler  $MENTAT_WRANGLER  (default: npx wrangler)
//   ssh       $MENTAT_SSH       (default: ssh)
//   npm       $MENTAT_NPM       (default: npm)
//   pbpaste   $MENTAT_PBPASTE   (default: pbpaste)
import { spawnSync } from 'node:child_process';

const DEFAULTS = {
  wrangler: ['MENTAT_WRANGLER', ['npx', 'wrangler']],
  ssh: ['MENTAT_SSH', ['ssh']],
  npm: ['MENTAT_NPM', ['npm']],
  pbpaste: ['MENTAT_PBPASTE', ['pbpaste']],
};

/** `[file, ...leadingArgs]` for a tool name; `node` is this very node binary. */
export function toolArgv(name, env = process.env) {
  if (name === 'node') return [process.execPath];
  const def = DEFAULTS[name];
  if (!def) throw new Error(`unknown tool: ${name}`);
  return env[def[0]] ? [env[def[0]]] : def[1];
}

/**
 * Run a tool. `input` goes to stdin (the only way a secret is ever handed to
 * a child); stdout and stderr are captured, never echoed here.
 * → { status, stdout, stderr }
 */
export function runTool(name, args, { input, cwd, env = process.env } = {}) {
  const [file, ...lead] = toolArgv(name, env);
  const r = spawnSync(file, [...lead, ...args], {
    cwd,
    env,
    input: input ?? '',
    encoding: 'utf8',
    maxBuffer: 512 * 1024 * 1024,
  });
  if (r.error) return { status: 127, stdout: '', stderr: String(r.error.message) };
  return { status: r.status ?? 1, stdout: r.stdout ?? '', stderr: r.stderr ?? '' };
}
