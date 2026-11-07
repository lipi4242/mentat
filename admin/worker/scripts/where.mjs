#!/usr/bin/env node
// `npm run where`: what this admin holds and where the user sees it — the
// models, their fields, the list/form URL of each, how to sign in. Read-only,
// from config/models.json and worker/.dev.vars; the agent's AGENTS.md block
// points here. `npm run where -- --url https://admin.example.com` for a remote one.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { flag, ROOT, WORKER_DIR } from './lib/d1.mjs';
import { parseDevVars } from './lib/local-config.mjs';
import { whereLines } from './lib/onboard.mjs';

const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : '');
const vars = parseDevVars(read(join(WORKER_DIR, '.dev.vars')));
const origin = flag(process.argv, '--url') ?? vars.BETTER_AUTH_URL;
if (!origin) {
  console.error('where: no URL — this is not a `connect --local` admin; pass --url <admin-url>');
  process.exit(1);
}
const text = read(join(ROOT, 'config', 'models.json'));
const models = text ? JSON.parse(text) : {};
const owners = (vars.ADMIN_EMAILS ?? '').split(',').map((s) => s.trim()).filter(Boolean);
console.log(whereLines({ origin, models, local: !!vars.BETTER_AUTH_URL && !flag(process.argv, '--url'), owners }).join('\n'));
