// The product/instance split: the committed wrangler.toml must stay free of
// instance data, and config/instance.mjs must turn an instance file into a
// complete deploy config. Runs the real script as a child process against the
// committed example file — never against a real instance.
import { describe, it, expect } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SCRIPT = join(ROOT, 'config', 'instance.mjs');
const EXAMPLE = join(ROOT, 'config', 'instance.example.json');
const product = readFileSync(join(ROOT, 'worker', 'wrangler.toml'), 'utf8');

describe('committed worker/wrangler.toml (product config)', () => {
  it('carries no Cloudflare account and no real D1 id', () => {
    expect(product).not.toMatch(/^\s*account_id\s*=/m);
    expect(product).toMatch(/^database_id = "local-dev-only"$/m);
  });

  it('names only example/localhost addresses in [vars]', () => {
    const vars = product.split('[vars]')[1].split(/^\[/m)[0];
    for (const m of vars.matchAll(/[\w.+-]+@([\w.-]+)/g)) expect(m[1]).toBe('example.com');
    for (const m of vars.matchAll(/https?:\/\/([\w.-]+)/g)) expect(m[1]).toMatch(/^(localhost|127\.0\.0\.1)$/);
  });
});

describe('config/instance.mjs render', () => {
  const run = (env: Record<string, string>) => {
    const out = mkdtempSync(join(tmpdir(), 'mentat-instance-'));
    const res = spawnSync('node', [SCRIPT, 'render', '--out', out], {
      env: { ...process.env, ...env },
      encoding: 'utf8',
    });
    return { out, res };
  };

  it('merges the instance file into a complete deploy config', () => {
    const { out, res } = run({ MENTAT_ADMIN_INSTANCE: EXAMPLE });
    expect(res.status, res.stderr).toBe(0);
    const ex = JSON.parse(readFileSync(EXAMPLE, 'utf8'));
    const toml = readFileSync(join(out, 'wrangler.toml'), 'utf8');
    expect(toml).toContain(`account_id = "${ex.cloudflare.account_id}"`);
    expect(toml).toContain(`database_id = "${ex.worker.database_id}"`);
    expect(toml).not.toMatch(/database_id = "local-dev-only"/);
    expect(toml).toContain(`INSTANCE_TITLE = "${ex.title}"`);
    expect(toml).toContain(`ADMIN_EMAILS = "${ex.worker.vars.ADMIN_EMAILS}"`);
    // the product's local-dev vars are gone, not merely shadowed
    expect(toml).not.toContain('Mentat Admin (dev)');
    expect(toml.match(/^OTP_SENDER = /gm)).toHaveLength(1);
    // paths still point back at worker/ from the rendered location
    expect(toml).toMatch(/^main = ".*worker\/src\/index\.ts"$/m);
    expect(toml).toMatch(/migrations_dir = ".*worker\/migrations"/);
    expect(readFileSync(join(out, '.env.production.local'), 'utf8')).toContain(
      `VITE_INSTANCE_TITLE="${ex.title}"`,
    );
  });

  it('refuses a wrong explicit path instead of falling back to another instance', () => {
    const { res } = run({ MENTAT_ADMIN_INSTANCE: join(ROOT, 'config', 'nope.json') });
    expect(res.status).toBe(1);
    expect(res.stderr).toContain('missing file');
  });

  it('refuses an instance file with a required key left empty', () => {
    const tmp = mkdtempSync(join(tmpdir(), 'mentat-instance-bad-'));
    const bad = join(tmp, 'instance.json');
    const ex = JSON.parse(readFileSync(EXAMPLE, 'utf8'));
    ex.worker.vars.OTP_SENDER = ' ';
    execFileSync('node', ['-e', `require('fs').writeFileSync(${JSON.stringify(bad)}, ${JSON.stringify(JSON.stringify(ex))})`]);
    const { res } = run({ MENTAT_ADMIN_INSTANCE: bad });
    expect(res.status).toBe(1);
    expect(res.stderr).toContain('worker.vars.OTP_SENDER');
  });
});
