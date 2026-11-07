#!/usr/bin/env node
// A one-time sign-in link for the LOCAL admin — no mailbox, no log reading.
//
//   npm run login-link              for the owner in worker/.dev.vars (ADMIN_EMAILS)
//   npm run login-link -- --email anna@example.com
//
// Valid for 10 minutes, once, and only on this machine (localhost — over an
// SSH tunnel too). The worker side and why it is safe: src/core/local-login.ts.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { d1Query, flag, WORKER_DIR } from './lib/d1.mjs';
import { parseDevVars } from './lib/local-config.mjs';
import { newLink, TTL_MINUTES } from './lib/login-link.mjs';

const devVarsPath = join(WORKER_DIR, '.dev.vars');
if (!existsSync(devVarsPath)) {
  console.error('login-link: no worker/.dev.vars — this is for a local admin set up by `npm run connect -- … --local`');
  process.exit(1);
}
const vars = parseDevVars(readFileSync(devVarsPath, 'utf8'));
const email = flag(process.argv.slice(2), '--email') ?? (vars.ADMIN_EMAILS ?? '').split(',')[0];
try {
  const link = newLink({ origin: vars.BETTER_AUTH_URL ?? 'http://localhost:8787', email });
  await d1Query('local')(link.sql);
  console.log(`Belépő link ${email} számára (egyszer használható, ${TTL_MINUTES} percig érvényes, csak ezen a gépen):`);
  console.log(`  ${link.url}`);
} catch (err) {
  console.error(`login-link: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
