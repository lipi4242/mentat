#!/usr/bin/env node
// The local admin: API + the built admin UI on one port (what the systemd
// unit of `connect --local` runs). Regenerates config/rendered/wrangler.local.toml
// from worker/wrangler.toml first, so a `git pull` is picked up on restart.
//
//   npm run dev:local -- --port 8787        (no systemd, e.g. macOS)
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { flag, ROOT, WORKER_DIR } from './lib/d1.mjs';
import { localConfigPath, renderLocalWrangler, wranglerDevArgs } from './lib/local-config.mjs';

const port = Number(flag(process.argv.slice(2), '--port') ?? 8787);
const out = localConfigPath(ROOT);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, renderLocalWrangler(readFileSync(join(WORKER_DIR, 'wrangler.toml'), 'utf8'), { root: ROOT }));
if (!existsSync(join(ROOT, 'admin', 'dist', 'index.html'))) {
  console.error('local-dev: no admin/dist — the UI is not built; run: npm --prefix ../admin run build (the API still starts)');
  mkdirSync(join(ROOT, 'admin', 'dist'), { recursive: true });
}
const wrangler = join(WORKER_DIR, 'node_modules', 'wrangler', 'bin', 'wrangler.js');
const r = spawnSync(process.execPath, [wrangler, ...wranglerDevArgs({ root: ROOT, port })], {
  cwd: WORKER_DIR,
  stdio: 'inherit',
  env: { ...process.env, WRANGLER_SEND_METRICS: 'false' },
});
process.exit(r.status ?? 1);
