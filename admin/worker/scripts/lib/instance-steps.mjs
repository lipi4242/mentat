// The README's "Set up your own instance" sequence as ordered steps. Each
// step reads what earlier steps stored in `v` (state.values) and stores what
// later ones need. A step that is done is never run again — so the auth
// secret is set once, not rotated on every rerun.
//
// Order note: the Pages project is created BEFORE the instance file, because
// its URL is the instance's ALLOWED_ORIGINS / SITE_URL and BETTER_AUTH_URL.
// The worker deploys before its secrets are put: `secret put` on a worker
// that does not exist yet would ask a question no script can answer.
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT, WORKER_DIR } from './d1.mjs';
import { alreadyExists, findDatabase, parseAccountId, parseDatabaseId, parsePagesUrl, parseWorkersUrl } from './instance-parse.mjs';
import { instanceJson } from './instance-state.mjs';

const ADMIN_DIR = join(ROOT, 'admin');

/** @param {any} o checked options  @param {any} p instancePaths  → step list */
export function instanceSteps(o, p) {
  const cfg = ['--config', join(p.rendered, 'wrangler.toml')];
  const render = (x) => x.sh('node', [join(ROOT, 'config', 'instance.mjs'), 'render', '--out', p.rendered]);
  return [
    {
      id: 'account', what: o.accountId ? `use account ${o.accountId}` : 'wrangler whoami → account id',
      run: (x, v) => { v.account_id = o.accountId ?? parseAccountId(x.sh('wrangler', ['whoami'])); },
    },
    {
      id: 'd1', what: `wrangler d1 create ${o.database}${o.location ? ` --location ${o.location}` : ''} (existing: d1 list --json)`,
      run: (x, v) => {
        const r = x.try('wrangler', ['d1', 'create', o.database, ...(o.location ? ['--location', o.location] : [])]);
        if (r.status === 0) return void (v.database_id = parseDatabaseId(r.stdout + r.stderr), (v.database_preexisting = false));
        if (!alreadyExists(r.stdout + r.stderr)) throw new Error(r.stderr.trim() || r.stdout.trim());
        v.database_id = findDatabase(x.sh('wrangler', ['d1', 'list', '--json']), o.database);
        v.database_preexisting = true;
      },
    },
    {
      id: 'pages-project', what: `wrangler pages project create ${o.pages} --production-branch=main (existing is fine)`,
      run: (x, v) => {
        const r = x.try('wrangler', ['pages', 'project', 'create', o.pages, '--production-branch=main']);
        if (r.status !== 0 && !alreadyExists(r.stdout + r.stderr)) throw new Error(r.stderr.trim() || r.stdout.trim());
        v.pages_url = (r.status === 0 && parsePagesUrl(r.stdout + r.stderr)) || `https://${o.pages}.pages.dev`;
      },
    },
    {
      id: 'instance-file', what: `write ${p.instance}`,
      run: (_x, v) => {
        if (existsSync(p.instance)) throw new Error(`${p.instance} already exists and this run did not write it — move it away or pick another --name`);
        mkdirSync(p.dir, { recursive: true, mode: 0o700 });
        writeFileSync(p.instance, JSON.stringify(instanceJson(o, v), null, 2) + '\n', { mode: 0o600, flag: 'wx' });
      },
    },
    {
      id: 'migrate', what: 'apply worker/migrations to the remote D1 (an existing database is backed up first)',
      run: (x, v) => {
        if (v.database_preexisting) x.sh('node', [join(WORKER_DIR, 'scripts', 'export.mjs'), '--remote', '--backup']);
        render(x);
        x.sh('wrangler', ['d1', 'migrations', 'apply', 'DB', '--remote', ...cfg]);
      },
    },
    {
      id: 'worker-deploy', what: `wrangler deploy (${o.worker}) → workers.dev URL`,
      run: (x, v) => { render(x); v.worker_url = parseWorkersUrl(x.sh('wrangler', ['deploy', ...cfg])); },
    },
    {
      id: 'secret-auth', what: 'wrangler secret put BETTER_AUTH_SECRET (random, via stdin, never shown)',
      run: (x) => { x.sh('wrangler', ['secret', 'put', 'BETTER_AUTH_SECRET', ...cfg], { input: randomBytes(48).toString('base64url') }); },
    },
    {
      id: 'secret-auth-url', what: 'wrangler secret put BETTER_AUTH_URL (= the Pages URL)',
      run: (x, v) => { x.sh('wrangler', ['secret', 'put', 'BETTER_AUTH_URL', ...cfg], { input: v.pages_url }); },
    },
    {
      id: 'pages-api-origin', what: `wrangler pages secret put API_ORIGIN --project-name=${o.pages} (= the worker URL)`,
      run: (x, v) => { x.sh('wrangler', ['pages', 'secret', 'put', 'API_ORIGIN', `--project-name=${o.pages}`], { input: v.worker_url }); },
    },
    {
      id: 'admin-deploy', what: `build the admin, wrangler pages deploy dist --project-name=${o.pages}`,
      run: (x) => {
        // VITE_ variables in the environment win over admin/.env.* files.
        x.sh('npm', ['run', 'build'], { cwd: ADMIN_DIR, env: { VITE_INSTANCE_TITLE: o.title } });
        // From admin/: wrangler finds the Pages Functions (admin/functions/) via the cwd.
        x.sh('wrangler', ['pages', 'deploy', 'dist', `--project-name=${o.pages}`, '--branch=main'], { cwd: ADMIN_DIR });
      },
    },
  ];
}

/** Optional last step: RESEND_API_KEY from the clipboard, straight into stdin. */
export function resendStep(o) {
  return {
    id: 'resend-key', what: 'pbpaste → wrangler secret put RESEND_API_KEY (never shown)',
    run: (x) => {
      const key = x.sh('pbpaste', []).trim();
      if (!key) throw new Error('the clipboard is empty — copy the Resend API key first');
      x.sh('wrangler', ['secret', 'put', 'RESEND_API_KEY', '--name', o.worker], { input: key });
    },
  };
}

/** The exact command for the manual Resend step. */
export function resendCommand(o, v) {
  return `CLOUDFLARE_ACCOUNT_ID=${v.account_id ?? '<account-id>'} npx wrangler secret put RESEND_API_KEY --name ${o.worker}`;
}
