// Where `instance:create` keeps one instance, and what it remembers between
// runs. Per slug, in ~/.config/mentat-admin/:
//
//   <slug>.json         the instance file (config/instance.mjs reads it via
//                       MENTAT_ADMIN_INSTANCE) — no secrets in it
//   <slug>.state.json   the steps done and the values they produced, so a
//                       rerun after a failure continues where it stopped
//   <slug>.rendered/    the rendered wrangler.toml the steps deploy with
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,30}$/;
const EMAIL_RE = /^[^\s@,]+@[^\s@,]+\.[^\s@,]+$/;

export function instancePaths(slug, home = homedir()) {
  const dir = join(home, '.config', 'mentat-admin');
  return {
    dir,
    instance: join(dir, `${slug}.json`),
    state: join(dir, `${slug}.state.json`),
    rendered: join(dir, `${slug}.rendered`),
  };
}

/** The CLI options → a checked, normalized request. Throws on a bad one. */
export function checkOptions({ name, title, adminEmails, otpSender, location, accountId }) {
  if (!name || !SLUG_RE.test(name)) throw new Error('--name must be a slug: lowercase letters, digits, dashes (max 31)');
  if (!title || !String(title).trim()) throw new Error('--title is required');
  const emails = String(adminEmails ?? '').split(',').map((e) => e.trim().toLowerCase()).filter(Boolean);
  if (!emails.length || emails.some((e) => !EMAIL_RE.test(e))) throw new Error('--admin-emails must be a comma-separated list of e-mail addresses');
  if (!otpSender || !EMAIL_RE.test(otpSender)) throw new Error('--otp-sender must be an e-mail address (on a domain verified in Resend)');
  if (location !== undefined && !/^[a-z]{4}$/.test(location)) throw new Error('--location must be a D1 location hint such as weur, eeur, enam');
  if (accountId !== undefined && !/^[0-9a-f]{32}$/.test(accountId)) throw new Error('--account-id must be 32 hex characters');
  return {
    slug: name,
    title: String(title).trim(),
    adminEmails: emails.join(','),
    otpSender: otpSender.toLowerCase(),
    location,
    accountId,
    database: `mentat-admin-${name}`,
    worker: `mentat-admin-api-${name}`,
    pages: `mentat-admin-${name}`,
  };
}

export function loadState(path) {
  if (!existsSync(path)) return { schema: 1, done: [], values: {} };
  const s = JSON.parse(readFileSync(path, 'utf8'));
  if (s.schema !== 1) throw new Error(`${path}: unknown schema ${s.schema}`);
  return s;
}

/** Atomic: a crash mid-write leaves the previous state, never half of one. */
export function saveState(path, state) {
  mkdirSync(join(path, '..'), { recursive: true, mode: 0o700 });
  writeFileSync(`${path}.tmp`, JSON.stringify(state, null, 2) + '\n', { mode: 0o600 });
  renameSync(`${path}.tmp`, path);
}

/** The instance file (shape: config/instance.example.json). */
export function instanceJson(opts, values) {
  return {
    _doc: `Written by npm run instance:create -- --name ${opts.slug}. Rendered by config/instance.mjs (MENTAT_ADMIN_INSTANCE=<this file>).`,
    title: opts.title,
    cloudflare: { account_id: values.account_id },
    worker: {
      name: opts.worker,
      database_name: opts.database,
      database_id: values.database_id,
      vars: {
        ALLOWED_ORIGINS: values.pages_url,
        ADMIN_EMAILS: opts.adminEmails,
        OTP_SENDER: opts.otpSender,
        SITE_URL: values.pages_url,
      },
    },
    admin: { pages_project: opts.pages },
  };
}
