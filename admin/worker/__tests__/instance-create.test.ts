// `instance:create` end to end against a fake wrangler / npm / pbpaste and a
// temp HOME. The instance renderer (config/instance.mjs) is the real one.
import { describe, it, expect } from 'vitest';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fakeBins } from './fake-bins';

const CLI = join(__dirname, '..', 'scripts', 'instance-create.mjs');
const ACCOUNT = 'abcdef0123456789abcdef0123456789';
const DB_ID = '11111111-2222-4333-8444-555555555555';
const OK_RULES = [
  { match: '^whoami', stdout: `│ Example's Account │ ${ACCOUNT} │\n` },
  { match: '^d1 create', stdout: `[[d1_databases]]\nbinding = "DB"\ndatabase_name = "mentat-admin-acme"\ndatabase_id = "${DB_ID}"\n` },
  { match: '^d1 execute', stdout: '[{"results":[]}]' },
  { match: '^d1 list --json', stdout: JSON.stringify([{ uuid: DB_ID, name: 'mentat-admin-acme' }]) },
  { match: '^pages project create', stdout: 'It will be available at https://mentat-admin-acme-x1y.pages.dev/ once you deploy.\n' },
  { match: '^deploy', stdout: 'Deployed mentat-admin-api-acme triggers\n  https://mentat-admin-api-acme.example.workers.dev\n' },
];
const ARGS = ['--name', 'acme', '--title', 'Acme Admin', '--admin-emails', 'Owner@acme.example,ops@acme.example', '--otp-sender', 'admin@acme.example', '--location', 'weur'];
const ORDER = [
  'whoami', 'd1 create', 'pages project create', 'd1 migrations apply', 'deploy', 'secret put BETTER_AUTH_SECRET',
  'secret put BETTER_AUTH_URL', 'pages secret put API_ORIGIN', 'npm run build', 'pages deploy dist',
];

function setup() {
  const bins = fakeBins();
  const home = mkdtempSync(join(tmpdir(), 'home-'));
  const run = (extra: string[] = [], env: Record<string, string> = {}) =>
    spawnSync(process.execPath, [CLI, ...ARGS, ...extra], { encoding: 'utf8', env: { PATH: process.env.PATH, HOME: home, ...bins.env, ...env } });
  const dir = join(home, '.config', 'mentat-admin');
  const label = (c: { argv: string[]; tool?: string }) => (c.tool ? `${c.tool} ${c.argv.join(' ')}` : c.argv.join(' '));
  const order = () => bins.calls().map(label).map((l) => ORDER.find((o) => l.startsWith(o)) ?? l);
  return { bins, home, run, dir, order };
}

describe('instance:create', () => {
  it('--dry-run lists the steps in order and runs nothing', () => {
    const t = setup();
    const r = t.run(['--dry-run']);
    expect(r.status, r.stderr).toBe(0);
    const ids = [...r.stdout.matchAll(/^\s+\d+\. ([a-z0-9-]+)/gm)].map((m) => m[1]);
    expect(ids).toEqual(['account', 'd1', 'pages-project', 'instance-file', 'migrate', 'worker-deploy', 'secret-auth', 'secret-auth-url', 'pages-api-origin', 'admin-deploy']);
    expect(r.stdout).toContain('secret put RESEND_API_KEY --name mentat-admin-api-acme');
    expect(t.bins.calls()).toEqual([]);
    expect(existsSync(t.dir)).toBe(false);
  });

  it('runs every step in order; the secret travels only on stdin', () => {
    const t = setup();
    t.bins.setRules(OK_RULES);
    const r = t.run();
    expect(r.status, r.stdout + r.stderr).toBe(0);
    expect(t.order()).toEqual(ORDER);

    const calls = t.bins.calls();
    const secret = calls.find((c) => c.argv.join(' ').startsWith('secret put BETTER_AUTH_SECRET'))!.stdin;
    expect(secret.length).toBeGreaterThanOrEqual(64);
    const everythingElse = [r.stdout, r.stderr, JSON.stringify(calls.map((c) => c.argv)), readFileSync(join(t.dir, 'acme.state.json'), 'utf8'), readFileSync(join(t.dir, 'acme.json'), 'utf8')];
    for (const text of everythingElse) expect(text).not.toContain(secret);
    expect(calls.find((c) => c.argv.join(' ').startsWith('secret put BETTER_AUTH_URL'))!.stdin).toBe('https://mentat-admin-acme-x1y.pages.dev');
    expect(calls.find((c) => c.argv.join(' ').startsWith('pages secret put API_ORIGIN'))!.stdin).toBe('https://mentat-admin-api-acme.example.workers.dev');
    expect(calls.find((c) => c.tool === 'npm')).toBeDefined();
    expect(calls.find((c) => c.argv[0] === 'd1' && c.argv[1] === 'create')!.argv).toEqual(['d1', 'create', 'mentat-admin-acme', '--location', 'weur']);

    const inst = JSON.parse(readFileSync(join(t.dir, 'acme.json'), 'utf8'));
    expect(inst).toMatchObject({
      title: 'Acme Admin',
      cloudflare: { account_id: ACCOUNT },
      worker: { name: 'mentat-admin-api-acme', database_id: DB_ID, vars: { ADMIN_EMAILS: 'owner@acme.example,ops@acme.example', ALLOWED_ORIGINS: 'https://mentat-admin-acme-x1y.pages.dev' } },
      admin: { pages_project: 'mentat-admin-acme' },
    });
    expect(statSync(t.dir).mode & 0o777).toBe(0o700);
    expect(readFileSync(join(t.dir, 'acme.rendered', 'wrangler.toml'), 'utf8')).toContain(`database_id = "${DB_ID}"`);
    expect(r.stdout).toContain(`CLOUDFLARE_ACCOUNT_ID=${ACCOUNT} npx wrangler secret put RESEND_API_KEY --name mentat-admin-api-acme`);
  });

  it('resumes after a mid-sequence failure without redoing done steps', () => {
    const t = setup();
    t.bins.setRules([{ match: '^deploy', status: 1, stderr: 'boom: deploy failed\n' }, ...OK_RULES]);
    const first = t.run();
    expect(first.status).toBe(1);
    expect(first.stdout).toMatch(/worker-deploy: FAILED[\s\S]*boom/);
    expect(t.order()).toEqual(ORDER.slice(0, 5));

    t.bins.setRules(OK_RULES);
    const second = t.run();
    expect(second.status, second.stdout + second.stderr).toBe(0);
    expect(t.order()).toEqual([...ORDER.slice(0, 5), ...ORDER.slice(4)]);
    expect(second.stdout).toMatch(/instance-file: done earlier, skipped/);
  });

  it('finds an already existing database instead of failing', () => {
    const t = setup();
    t.bins.setRules([{ match: '^d1 create', status: 1, stderr: 'A database with that name already exists\n' }, ...OK_RULES]);
    const r = t.run();
    expect(r.status, r.stdout + r.stderr).toBe(0);
    expect(JSON.parse(readFileSync(join(t.dir, 'acme.json'), 'utf8')).worker.database_id).toBe(DB_ID);
    // An existing database may hold data: it is backed up (export --backup) before migrating,
    // through the instance's own rendered config, not the checkout's.
    const exp = t.bins.calls().find((c) => c.argv[0] === 'd1' && c.argv[1] === 'execute')!;
    expect(exp.argv).toContain(join(t.dir, 'acme.rendered', 'wrangler.toml'));
    expect(t.order().indexOf('d1 migrations apply')).toBeGreaterThan(t.bins.calls().indexOf(exp));
  });

  it('--resend-from-clipboard pipes the key to wrangler without showing it', () => {
    const t = setup();
    t.bins.setRules(OK_RULES);
    const key = 're_FAKE_resend_key_123456';
    const r = t.run(['--resend-from-clipboard'], { FAKE_CLIPBOARD: key });
    expect(r.status, r.stdout + r.stderr).toBe(0);
    const put = t.bins.calls().find((c) => c.argv.join(' ').startsWith('secret put RESEND_API_KEY'))!;
    expect(put.stdin).toBe(key);
    expect(JSON.stringify(t.bins.calls().map((c) => c.argv)) + r.stdout + r.stderr).not.toContain(key);
  });

  it('refuses to continue a state with different options', () => {
    const t = setup();
    t.bins.setRules(OK_RULES);
    expect(t.run().status).toBe(0);
    const r = spawnSync(process.execPath, [CLI, ...ARGS.slice(0, 3), 'Other', ...ARGS.slice(4)], { encoding: 'utf8', env: { PATH: process.env.PATH, HOME: t.home, ...t.bins.env } });
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/other options/);
  });
});
