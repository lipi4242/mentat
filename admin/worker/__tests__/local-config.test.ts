// The local admin's generated config: the UI on the API's port, and the
// .dev.vars values `connect --local` owns.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { renderLocalWrangler, updateDevVars, wranglerDevArgs } from '../scripts/lib/local-config.mjs';

const BASE = readFileSync(join(__dirname, '..', 'wrangler.toml'), 'utf8');
const EXAMPLE = readFileSync(join(__dirname, '..', '..', 'config', 'dev.vars.example'), 'utf8');
const vars = (text: string) =>
  Object.fromEntries(text.split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => l.split(/=(.*)/s).slice(0, 2)));

describe('renderLocalWrangler', () => {
  const out = renderLocalWrangler(BASE, { root: '/srv/mentat-admin' });

  it('serves the built admin UI from the same port, the API first', () => {
    expect(out).toContain('[assets]');
    expect(out).toContain('directory = "/srv/mentat-admin/admin/dist"');
    expect(out).toContain('not_found_handling = "single-page-application"');
    expect(out).toContain('run_worker_first = ["/api/*"]');
  });

  it('points main at the worker with an absolute path and keeps the local D1', () => {
    expect(out).toContain('main = "/srv/mentat-admin/worker/src/index.ts"');
    expect(out).toContain('database_id = "local-dev-only"');
  });
});

describe('wranglerDevArgs', () => {
  it('uses the worker dir for secrets and state, so migrate:local and the server share one D1', () => {
    const a = wranglerDevArgs({ root: '/r', port: 8787 });
    expect(a).toEqual([
      'dev', '--config', '/r/config/rendered/wrangler.local.toml',
      '--env-file', '/r/worker/.dev.vars', '--persist-to', '/r/worker/.wrangler/state',
      '--ip', '127.0.0.1', '--port', '8787',
    ]);
  });
});

describe('updateDevVars', () => {
  it('sets the URL, the owner and a fresh secret on the example', () => {
    const { text, email } = updateDevVars(EXAMPLE, { port: 9000, email: 'Anna@Example.com', secret: 's'.repeat(64) });
    const v = vars(text);
    expect(v.BETTER_AUTH_URL).toBe('http://localhost:9000');
    expect(v.ADMIN_EMAILS).toBe('anna@example.com');
    expect(v.BETTER_AUTH_SECRET).toBe('s'.repeat(64));
    expect(v.OTP_DRY_RUN).toBe('1');
    expect(v.ALLOWED_ORIGINS).toContain('http://localhost:9000');
    expect(email).toBe('anna@example.com');
    expect(text).toContain('# Local-only secrets'); // comments survive
  });

  it('keeps an owner and a real secret already there', () => {
    const first = updateDevVars(EXAMPLE, { port: 8787, email: 'anna@example.com', secret: 'a'.repeat(64) }).text;
    const { text, email } = updateDevVars(first, { port: 8787, secret: 'b'.repeat(64) });
    expect(vars(text).BETTER_AUTH_SECRET).toBe('a'.repeat(64));
    expect(email).toBe('anna@example.com');
    expect(text.match(/^ADMIN_EMAILS=/gm)!.length).toBe(1);
  });

  it('without --email and without an owner falls back to the product default', () => {
    expect(updateDevVars(EXAMPLE, { port: 8787, secret: 'c'.repeat(64) }).email).toBe('admin@example.com');
  });

  it('without --email takes the git-config address, so connect never has to ask who signs in', () => {
    const r = updateDevVars(EXAMPLE, { port: 8787, secret: 'c'.repeat(64), fallback: 'Owner@Example.com' });
    expect(r.email).toBe('owner@example.com');
    expect(vars(r.text).ADMIN_EMAILS).toBe('owner@example.com');
  });

  it('an owner already in .dev.vars beats the git address; an unusable git address falls back to the default', () => {
    const first = updateDevVars(EXAMPLE, { port: 8787, email: 'anna@example.com', secret: 'a'.repeat(64) }).text;
    expect(updateDevVars(first, { port: 8787, secret: 'b'.repeat(64), fallback: 'x@example.com' }).email).toBe('anna@example.com');
    expect(updateDevVars(EXAMPLE, { port: 8787, secret: 'c'.repeat(64), fallback: 'noreply@localhost' }).email).toBe('admin@example.com');
    expect(updateDevVars(EXAMPLE, { port: 8787, secret: 'c'.repeat(64), fallback: '' }).email).toBe('admin@example.com');
  });

  it('refuses something that is not one address', () => {
    expect(() => updateDevVars(EXAMPLE, { port: 8787, email: 'a@example.com,c@example.com', secret: 'x' })).toThrow(/e-mail/);
  });
});
