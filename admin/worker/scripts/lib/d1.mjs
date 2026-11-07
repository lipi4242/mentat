// The one place the scripts talk to D1: `wrangler d1 execute` against either
// the local (wrangler dev) database or the instance's remote one. The target
// is always explicit — a script that silently defaulted to --remote could
// write to the live database by accident.
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { toolArgv } from './tools.mjs';

export const WORKER_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const ROOT = dirname(WORKER_DIR);

/** `--local` or `--remote`, exactly one. Returns null when neither or both are given. */
export function parseTarget(argv) {
  const local = argv.includes('--local');
  const remote = argv.includes('--remote');
  if (local === remote) return null;
  return local ? 'local' : 'remote';
}

/** Value of `--name value`, or undefined. */
export function flag(argv, name) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
}

/** `--tables a,b` → ['a','b'], or undefined. */
export function tablesFlag(argv) {
  const v = flag(argv, '--tables');
  return v ? v.split(',').map((s) => s.trim()).filter(Boolean) : undefined;
}

function targetArgs(target) {
  if (target === 'local') return ['--local'];
  // The remote database is instance data: render its config first (README).
  // $MENTAT_RENDER_DIR (set by instance:create) renders outside the checkout.
  const out = process.env.MENTAT_RENDER_DIR;
  execFileSync('node', [join(ROOT, 'config', 'instance.mjs'), 'render', ...(out ? ['--out', out] : [])], { stdio: ['ignore', 'ignore', 'inherit'] });
  return ['--remote', '--config', join(out ?? join(ROOT, 'config', 'rendered'), 'wrangler.toml')];
}

function wrangler(args) {
  const [file, ...lead] = toolArgv('wrangler');
  return execFileSync(file, [...lead, 'd1', 'execute', 'DB', ...args], {
    cwd: WORKER_DIR,
    encoding: 'utf8',
    maxBuffer: 512 * 1024 * 1024,
    stdio: ['ignore', 'pipe', 'inherit'],
  });
}

/** `queryMany` for dump.mjs: one wrangler call, one result set per statement. */
export function d1Query(target) {
  const args = targetArgs(target);
  return async (sqls) => {
    if (!sqls.length) return [];
    const out = JSON.parse(wrangler([...args, '--json', '--command', sqls.join(';\n')]));
    if (out.length !== sqls.length) throw new Error(`expected ${sqls.length} result sets, got ${out.length}`);
    return out.map((r) => r.results ?? []);
  };
}

/** Run a SQL file against the target. */
export function d1ExecFile(target, file) {
  wrangler([...targetArgs(target), '--file', file]);
}
