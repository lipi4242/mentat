#!/usr/bin/env node
// The local admin's real state — the only thing an agent should quote about
// it (URL, port, commit, migrations, token scopes). Read-only.
//
//   npm run status            human/agent readable
//   npm run status -- --json
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { d1Query, ROOT, WORKER_DIR } from './lib/d1.mjs';
import { defaultRun, UNIT } from './lib/local-admin.mjs';
import { parseDevVars } from './lib/local-config.mjs';
import { formatStatus, pendingMigrations, portOfUnit } from './lib/status.mjs';

const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : '');
const git = (...a) => {
  try {
    return execFileSync('git', ['-C', ROOT, ...a], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return '';
  }
};
async function get(url) {
  try {
    return await fetch(url, { signal: AbortSignal.timeout(3000) });
  } catch {
    return null;
  }
}

const vars = parseDevVars(read(join(WORKER_DIR, '.dev.vars')));
const url = vars.BETTER_AUTH_URL;
const unitText = read(join(homedir(), '.config', 'systemd', 'user', UNIT));
const health = url ? await get(`${url}/api/health`) : null;
const ui = url ? await get(`${url}/`) : null;

const files = readdirSync(join(WORKER_DIR, 'migrations')).filter((f) => f.endsWith('.sql'));
let migrations;
let tokens = [];
try {
  const [applied, live] = await d1Query('local')([
    'SELECT name FROM d1_migrations ORDER BY id',
    `SELECT id, label, scopes, expires_at, last_used_at FROM agent_token
      WHERE active = 1 AND unixepoch(expires_at) > unixepoch('now') ORDER BY label`,
  ]);
  const names = applied.map((r) => r.name);
  migrations = { applied: names, pending: pendingMigrations(files, names) };
  tokens = live;
} catch (e) {
  migrations = { error: e instanceof Error ? e.message.split('\n')[0] : String(e) };
}

const facts = {
  url,
  unit: unitText ? defaultRun('systemctl', ['--user', 'is-active', UNIT]).stdout.trim() || 'unknown' : 'none',
  port: portOfUnit(unitText),
  health: !!health?.ok,
  ui: !!ui?.ok && (ui.headers.get('content-type') ?? '').includes('text/html'),
  version: JSON.parse(read(join(WORKER_DIR, 'package.json'))).version,
  commit: git('rev-parse', '--short', 'HEAD') || 'unknown',
  branch: git('branch', '--show-current') || 'detached',
  dirty: git('status', '--porcelain').split('\n').filter(Boolean).length,
  migrations,
  tokens,
  owners: (vars.ADMIN_EMAILS ?? '').split(',').map((s) => s.trim()).filter(Boolean),
};
console.log(process.argv.includes('--json') ? JSON.stringify(facts, null, 2) : formatStatus(facts));
