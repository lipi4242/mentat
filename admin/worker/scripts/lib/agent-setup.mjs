// The effectful steps `connect` does in the AGENT's repo beyond the token:
// vendor cases_cli into .mentat/bin, write the managed AGENTS.md block, move
// the brain's cases into the admin. All idempotent; each says what it did.
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { adminBlock, upsertBlock } from './onboard.mjs';
import { ROOT } from './d1.mjs';

const CLI_SRC = join(ROOT, 'agent', 'cases', 'cases_cli');
const skip = (p) => p.split('/').includes('__pycache__');

function files(dir, rel = '') {
  if (!existsSync(dir)) return [];
  return readdirSync(join(dir, rel), { withFileTypes: true }).flatMap((e) => {
    const r = join(rel, e.name);
    if (skip(r)) return [];
    return e.isDirectory() ? files(dir, r) : [r];
  });
}

/** 'current' | 'missing' | 'stale' for the vendored cases_cli. */
export function cliState(repo) {
  const dest = join(repo, '.mentat', 'bin', 'cases_cli');
  if (!existsSync(dest)) return 'missing';
  const a = files(CLI_SRC).sort();
  const b = files(dest).sort();
  if (a.join('\n') !== b.join('\n')) return 'stale';
  return a.every((f) => readFileSync(join(CLI_SRC, f)).equals(readFileSync(join(dest, f)))) ? 'current' : 'stale';
}

/** Copy cases_cli to <repo>/.mentat/bin; returns 'installed' | 'updated' | 'current'. */
export function installCli(repo) {
  const state = cliState(repo);
  if (state === 'current') return state;
  const dest = join(repo, '.mentat', 'bin', 'cases_cli');
  mkdirSync(join(repo, '.mentat', 'bin'), { recursive: true });
  rmSync(dest, { recursive: true, force: true });
  cpSync(CLI_SRC, dest, { recursive: true, filter: (s) => !skip(s) });
  return state === 'missing' ? 'installed' : 'updated';
}

export const blockState = (repo, opts) => {
  const p = join(repo, 'AGENTS.md');
  const text = existsSync(p) ? readFileSync(p, 'utf8') : '';
  const block = adminBlock(opts);
  if (!text.includes(block)) return { p, text, next: upsertBlock(text, block), state: text.includes('mentat:admin:start') ? 'stale' : 'missing' };
  return { p, text, next: text, state: 'current' };
};

/** Write the managed block; returns 'added' | 'updated' | 'current'. */
export function writeBlock(repo, opts) {
  const { p, next, state } = blockState(repo, opts);
  if (state === 'current') return state;
  writeFileSync(p, next);
  return state === 'missing' ? 'added' : 'updated';
}

/** Does this admin accept the token? (GET /api/meta is token-authenticated.) */
export async function tokenWorks(origin, token) {
  if (!token) return false;
  try {
    const r = await fetch(`${origin}/api/meta`, { headers: { 'X-Mentat-Token': token }, signal: AbortSignal.timeout(3000) });
    return r.ok;
  } catch {
    return false;
  }
}

export function envValue(repo, key) {
  const p = join(repo, '.env');
  if (!existsSync(p)) return '';
  const line = readFileSync(p, 'utf8').split('\n').find((l) => l.startsWith(`${key}=`));
  return line ? line.slice(key.length + 1).trim() : '';
}

/** `cases_cli migrate --to admin` (dry run first, one line quoted). Returns the exit code. */
export function migrateBrain(repo) {
  const cli = join(repo, '.mentat', 'bin', 'cases_cli');
  const run = (extra) => spawnSync('python3', [cli, 'migrate', '--to', 'admin', ...extra], { cwd: repo, encoding: 'utf8' });
  const dry = run(['--dry-run']);
  const line = (dry.stdout || dry.stderr || '').trim().split('\n')[0];
  console.log(`brain: ${line || 'nothing to move'}`);
  if (dry.status !== 0) return dry.status ?? 1;
  const real = run([]);
  if (real.status !== 0) console.error((real.stderr || real.stdout).trim());
  return real.status ?? 1;
}
