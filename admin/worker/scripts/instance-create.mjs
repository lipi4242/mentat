#!/usr/bin/env node
// Set up a new instance on Cloudflare — the README's "Set up your own
// instance" sequence, scripted:
//
//   npm run instance:create -- --name <slug> --title "<title>" --admin-emails anna@example.com,bela@example.com \
//       --otp-sender otp@example.com [--location weur] [--account-id <id>] [--dry-run] [--resend-from-clipboard]
//
// Needs `npx wrangler login` first. Names come from the slug: D1
// mentat-admin-<slug>, worker mentat-admin-api-<slug>, Pages mentat-admin-<slug>.
// The instance file lands in ~/.config/mentat-admin/<slug>.json; later
// commands select it with MENTAT_ADMIN_INSTANCE=<that file>.
//
// Resumable: ~/.config/mentat-admin/<slug>.state.json records the done
// steps; rerun the same command after a failure and it continues.
// --dry-run prints the ordered steps (and which are done) and runs nothing.
//
// Secrets go to wrangler only on stdin — never in argv, never printed.
// RESEND_API_KEY stays a manual step (the exact command is printed at the
// end) unless --resend-from-clipboard: then it is read with pbpaste and piped
// to `wrangler secret put` without being shown.
import { flag } from './lib/d1.mjs';
import { makeExec, runSteps } from './lib/instance-run.mjs';
import { checkOptions, instancePaths, loadState, saveState } from './lib/instance-state.mjs';
import { instanceSteps, resendCommand, resendStep } from './lib/instance-steps.mjs';

const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const fromClipboard = argv.includes('--resend-from-clipboard');

let o;
try {
  o = checkOptions({
    name: flag(argv, '--name'),
    title: flag(argv, '--title'),
    adminEmails: flag(argv, '--admin-emails'),
    otpSender: flag(argv, '--otp-sender'),
    location: flag(argv, '--location'),
    accountId: flag(argv, '--account-id'),
  });
} catch (err) {
  console.error(`instance:create: ${err instanceof Error ? err.message : err}`);
  console.error('usage: npm run instance:create -- --name <slug> --title <title> --admin-emails a,b --otp-sender <addr>\n' +
    '                       [--location weur] [--account-id <id>] [--dry-run] [--resend-from-clipboard]');
  process.exit(1);
}

const p = instancePaths(o.slug);
const state = loadState(p.state);
const steps = [...instanceSteps(o, p), ...(fromClipboard ? [resendStep(o)] : [])];

// A rerun must mean the same instance: different options would silently mix two.
const asked = { title: o.title, adminEmails: o.adminEmails, otpSender: o.otpSender, location: o.location ?? null };
if (state.options && JSON.stringify(state.options) !== JSON.stringify(asked)) {
  console.error(`instance:create: ${p.state} was started with other options:\n  ${JSON.stringify(state.options)}\n` +
    'rerun with those, or remove the state file to start over.');
  process.exit(1);
}

if (dryRun) {
  console.log(`[dry-run] instance "${o.slug}" — nothing is run. Steps in order:`);
  steps.forEach((s, i) => console.log(`  ${i + 1}. ${s.id}${state.done.includes(s.id) ? ' (done)' : ''}: ${s.what}`));
  if (!fromClipboard) console.log(`  then by hand: ${resendCommand(o, state.values)}`);
  process.exit(0);
}

state.options = asked;
saveState(p.state, state);
const ok = runSteps({ steps, state, statePath: p.state, exec: makeExec({ instanceFile: p.instance, renderDir: p.rendered, values: state.values }) });
if (!ok) process.exit(1);

const v = state.values;
console.log(`\nInstance "${o.slug}" is up.`);
console.log(`  admin:         ${v.pages_url}`);
console.log(`  API (worker):  ${v.worker_url}`);
console.log(`  instance file: ${p.instance}  (use with MENTAT_ADMIN_INSTANCE=${p.instance})`);
if (!fromClipboard) {
  console.log('\nLast step, by hand — the Resend API key (sign-in mail does not work without it).');
  console.log('Copy the key from Resend, then run (it asks for the value; nothing is echoed):\n');
  console.log(`  cd worker && ${resendCommand(o, v)}\n`);
  console.log('or rerun this command with --resend-from-clipboard.');
}
console.log('\nA custom domain later: add it to ALLOWED_ORIGINS / SITE_URL in the instance file, set BETTER_AUTH_URL to it, redeploy.');
