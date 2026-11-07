#!/usr/bin/env node
// Bind an agent repo to this admin (contract LG1). Mints a token and writes
//   <repo>/.env                 MENTAT_ADMIN_TOKEN=<token>   (0600, must be gitignored)
//   <repo>/.mentat/local.json   admin.url, admin.token_env    (must be gitignored)
//   <repo>/mentat.json          components.admin              (committed; no URL, no token)
// The token is never printed.
//
//   npm run connect -- --repo <path> --url <admin-url> --local|--remote
//       [--agent <name>] [--scope cases:write] [--days 90] [--token-env NAME] [--plugins cases]
//       [--email owner@example.com]   (--local: who signs in to the UI; default: the repo's git user.email, else admin@example.com)
//       [--migrate-brain] [--check]
//
// --agent defaults to mentat.json agent.name. Needs python3 for the shared
// .mentat/lock (fcntl.flock).
//
// --local is the one way to bind a local admin. Before minting it also
//   links node/npm/npx into ~/.local/bin (on the login PATH via ~/.profile),
//   writes worker/.dev.vars (URL, owner e-mail, a random secret; other lines
//   survive), builds the admin UI (admin/dist), applies the local migrations
//   (npm run migrate:local, with its backup), installs + starts the systemd
//   user unit mentat-admin.service (API + UI on the URL's port, at boot
//   thanks to linger) and waits for /api/health. It then finishes the agent's
//   side too: cases_cli into <repo>/.mentat/bin, the managed block at the END
//   of <repo>/AGENTS.md (<!-- mentat:admin:start -->), and with
//   --migrate-brain the brain's cases into the admin. Rerunning is safe: a
//   token the admin still accepts is kept, a current cases_cli/block is left.
//   --check changes nothing: it lists what is done and what is missing.
import { execFileSync } from 'node:child_process';
import { cliState, blockState, envValue, installCli, migrateBrain, tokenWorks, writeBlock } from './lib/agent-setup.mjs';
import { closingLines } from './lib/onboard.mjs';
import { randomBytes } from 'node:crypto';
import { chmodSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir, userInfo } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { connect } from './lib/connect.mjs';
import { mint } from './lib/mint.mjs';
import { d1Query, flag, parseTarget, ROOT, WORKER_DIR } from './lib/d1.mjs';
import { installService, linkNode, localPort, waitHealthy } from './lib/local-admin.mjs';
import { readJson } from './lib/manifest.mjs';
import { gitEmail, updateDevVars } from './lib/local-config.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
const repo = flag(argv, '--repo');
const url = flag(argv, '--url');
if (!target || !repo || !url) {
  console.error('usage: npm run connect -- --repo <path> --url <admin-url> --local|--remote [--agent N] [--scope S] [--days N] [--token-env NAME] [--plugins a,b] [--migrate-brain] [--check]');
  process.exit(1);
}
const plugins = flag(argv, '--plugins')?.split(',').filter(Boolean);
const cases = !plugins || plugins.includes('cases');
const tokenEnv = flag(argv, '--token-env') ?? 'MENTAT_ADMIN_TOKEN';
const home = homedir();
const dir = WORKER_DIR.startsWith(home + '/') ? `~${WORKER_DIR.slice(home.length)}` : WORKER_DIR;
const origin = new URL(url).origin;
const blockOpts = { origin, dir, local: target === 'local', cases };

async function setupLocal() {
  const port = localPort(url);
  const nodeBin = dirname(process.execPath);
  const { linked, skipped } = linkNode({ home: homedir(), nodeBin });
  if (linked.length) console.log(`node: ${linked.join(', ')} linked into ~/.local/bin (a new login shell finds them)`);
  if (skipped.length) console.log(`node: ~/.local/bin/${skipped.join(', ')} already exist and are not links — left alone`);
  const devVars = join(WORKER_DIR, '.dev.vars');
  const before = readFileSync(existsSync(devVars) ? devVars : join(ROOT, 'config', 'dev.vars.example'), 'utf8');
  const vars = updateDevVars(before, { port, email: flag(argv, '--email'), fallback: gitEmail(resolve(repo)), secret: randomBytes(32).toString('hex') });
  writeFileSync(devVars, vars.text, { mode: 0o600 });
  chmodSync(devVars, 0o600);
  const quiet = { stdio: ['ignore', 'ignore', 'inherit'] };
  if (!existsSync(join(ROOT, 'admin', 'node_modules'))) execFileSync('npm', ['ci', '--prefix', join(ROOT, 'admin')], quiet);
  execFileSync('npm', ['--prefix', join(ROOT, 'admin'), 'run', 'build'], quiet);
  execFileSync('npm', ['run', 'migrate:local'], { cwd: WORKER_DIR, stdio: ['ignore', 'inherit', 'inherit'] });
  const svc = installService({ home: homedir(), user: userInfo().username, workerDir: WORKER_DIR, nodeBin, port });
  if (!svc.installed) {
    console.log(`service: ${svc.reason}`);
    return vars.email;
  }
  console.log(`service: ${svc.unitPath} enabled${svc.linger ? ', starts at boot (linger on)' : ''}`);
  if (svc.hint) console.log(`service: ${svc.hint}`);
  if (!(await waitHealthy(new URL(url).origin))) {
    throw new Error(`the admin did not answer on ${new URL(url).origin}/api/health — see: journalctl --user -u mentat-admin.service`);
  }
  return vars.email;
}

async function check() {
  const rows = [];
  const row = (ok, what, fix) => rows.push(`${ok ? 'ok     ' : 'MISSING'} ${what}${ok ? '' : ` — ${fix}`}`);
  const health = await fetch(`${origin}/api/health`, { signal: AbortSignal.timeout(3000) }).then((r) => r.ok, () => false);
  row(health, `admin answers on ${origin}`, 'connect without --check starts it');
  row(await tokenWorks(origin, envValue(resolve(repo), tokenEnv)), `token in ${repo}/.env accepted`, 'connect mints one');
  const m = readJson(join(resolve(repo), 'mentat.json'));
  row(!!m?.components?.admin, 'mentat.json components.admin', 'connect writes it');
  if (cases) {
    row(cliState(resolve(repo)) === 'current', 'cases_cli current in .mentat/bin', 'connect copies it');
    row(m?.cases?.backend === 'admin', 'cases.backend = admin', '--migrate-brain moves the brain cases');
  }
  row(blockState(resolve(repo), blockOpts).state === 'current', 'AGENTS.md mentat:admin block', 'connect writes it');
  console.log(rows.join('\n'));
  const bad = rows.filter((r) => r.startsWith('MISSING')).length;
  console.log(bad ? `check: ${bad} missing — rerun without --check` : 'check: all in place');
  process.exit(bad ? 2 : 0);
}

try {
  if (argv.includes('--check')) await check();
  const owner = target === 'local' ? await setupLocal() : undefined;
  const repoAbs = resolve(repo);
  const nextSteps = [];
  const kept = await tokenWorks(origin, envValue(repoAbs, tokenEnv)) && !!readJson(join(repoAbs, 'mentat.json'))?.components?.admin;
  if (kept) {
    console.log(`token: the one in ${repo}/.env is still accepted — kept (revoke/rotate: npm run revoke-token)`);
  } else {
    const query = d1Query(target);
    const out = await connect({
      repo: repoAbs,
      url,
      agent: flag(argv, '--agent'),
      scopes: flag(argv, '--scope') ?? 'cases:write',
      days: flag(argv, '--days'),
      tokenEnv,
      plugins,
      mintFn: (req) => mint(query, req),
    });
    console.log(`connected ${out.label} → ${out.url}`);
    console.log(`  token ${out.id} (scopes "${out.scopes}", expires ${out.expires_at} UTC) in ${out.envFile} as ${out.tokenEnv}`);
    console.log(`  revoke: npm run revoke-token -- --id ${out.id} --${target}`);
  }
  if (cases) console.log(`cases_cli: ${installCli(repoAbs)} in .mentat/bin`);
  console.log(`AGENTS.md: mentat:admin block ${writeBlock(repoAbs, blockOpts)}`);
  if (argv.includes('--migrate-brain') && cases) {
    if (migrateBrain(repoAbs) !== 0) throw new Error('migrating the brain cases failed — rerun connect with --migrate-brain (a rerun finishes it)');
  } else if (cases && readJson(join(repoAbs, 'mentat.json'))?.cases?.backend !== 'admin') {
    nextSteps.push('python3 .mentat/bin/cases_cli migrate --to admin   (or rerun with --migrate-brain)');
  }
  nextSteps.push('python3 .mentat/bin/cases_cli sync at session start');
  console.log(closingLines({ origin, dir, local: target === 'local', cases, nextSteps }).join('\n'));
  if (owner) console.log(`owner: ${owner} (change: --email)`);
} catch (err) {
  console.error(`connect: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
