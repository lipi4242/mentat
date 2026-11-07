#!/usr/bin/env node
// Extend the admin in ONE command — the whole of agent/EXTENDING.md:
//
//   npm run model -- add-field <model> <field> --type integer --min 0 --label "Összeg (Ft)" [--required]
//   npm run model -- new <entity> --label "Ügyfelek" --field nev:text:required --field email:email [--ref other]
//       [--check]  validate + show what it would do, change nothing     [--repo <agent repo>]  token for the probe + widened to the entity
//   npm run model -- --help          the full syntax
//
// It validates the request, edits config/models.json (once), generates the
// 09NN migration (model:migration), migrates the local database (backup
// first), looks at the running admin (/api/meta without "pending", one
// invalid value refused), commits both files on the local instance branch,
// and ends with the list/form URL and the agent's commands. Re-running the
// same request is harmless. A model:migration failure rolls the file back.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { ROOT, WORKER_DIR } from './lib/d1.mjs';
import { commitInstance, writeInstanceFile } from './lib/instance-files.mjs';
import { parseDevVars } from './lib/local-config.mjs';
import { addField, newEntity, parseArgs, UsageError } from './lib/model-spec.mjs';
import { findToken, probe } from './lib/model-probe.mjs';
import { d1Query } from './lib/d1.mjs';
import { helpText, helpTopic } from './lib/model-help.mjs';
import { newLink } from './lib/login-link.mjs';
import { widenToken } from './lib/model-scope.mjs';
import { usage } from './lib/model-report.mjs';

const MODELS = join(ROOT, 'config', 'models.json');
const MIGRATIONS = join(WORKER_DIR, 'migrations');
const say = (s) => console.log(`model: ${s}`);

function migrate(slug, extra, env = process.env) {
  const r = spawnSync(process.execPath, [join(WORKER_DIR, 'scripts', 'model-migration.mjs'), slug, ...extra], { cwd: WORKER_DIR, encoding: 'utf8', env });
  return { ok: r.status === 0, out: r.stdout ?? '', err: r.stderr ?? '' };
}

function main() {
  const topic = helpTopic(process.argv.slice(2));
  if (topic) { console.log(helpText(topic)); return 0; }
  const { cmd, rest, flags, fields } = parseArgs(process.argv.slice(2));
  const raw = readFileSync(MODELS, 'utf8');
  const doc = JSON.parse(raw);
  const models = { ...doc, fields: doc.fields ?? {}, entities: doc.entities ?? [] };
  if (cmd !== 'add-field' && cmd !== 'new') throw new UsageError(`unknown command "${cmd ?? ''}" — add-field | new`);
  if (cmd === 'add-field' && fields.length) throw new UsageError('add-field takes --type/--label…, not --field (that is for new)');
  const plan = cmd === 'add-field' ? addField(models, rest, flags) : newEntity(models, rest, flags, fields);
  const what = plan.field ? `${plan.target.name}.${plan.field.name} (${plan.field.type})` : `${plan.target.name} (${plan.models.entities.find((e) => e.name === plan.target.name).fields.map((f) => f.name).join(', ')})`;

  if (flags.check) {
    const dir = mkdtempSync(join(tmpdir(), 'model-check-'));
    const file = join(dir, 'models.json');
    writeFileSync(file, `${JSON.stringify(plan.models, null, 2)}\n`);
    const m = migrate('check', ['--dry-run'], { ...process.env, MENTAT_MODELS_FILE: file });
    rmSync(dir, { recursive: true, force: true });
    say(`--check: ${what} is valid${plan.changed ? '' : ' and already declared'}; nothing was changed. The migration it would write:`);
    console.log(m.ok ? m.out.trim() : m.err.trim());
    return 0;
  }

  const before = new Set(readdirSync(MIGRATIONS));
  if (plan.changed) writeInstanceFile(MODELS, `${JSON.stringify(plan.models, null, 2)}\n`);
  const m = migrate(plan.slug, ['--no-commit']);
  if (!m.ok) {
    if (plan.changed) writeInstanceFile(MODELS, raw);
    for (const f of readdirSync(MIGRATIONS)) if (!before.has(f)) rmSync(join(MIGRATIONS, f));
    console.error(`${m.out}${m.err}`.trim());
    console.error('model: FAILED — rolled back (config/models.json and the new migration file restored). Fix the cause above, then rerun the same command.');
    return 1;
  }
  const mig = /wrote worker\/migrations\/(\S+)/.exec(m.out)?.[1] ?? null;
  say(`${what} declared${mig ? `, migration ${mig} written and applied locally (backup first)` : '; the schema already matched, no migration'}`);

  let commit = 'nothing to commit (already committed)';
  const files = ['config/models.json', ...(mig ? [`worker/migrations/${mig}`] : [])];
  if (plan.changed || mig) {
    const c = commitInstance({ root: ROOT, files, message: `chore(peldany): ${plan.slug} — models.json${mig ? ` + ${mig}` : ''}` });
    commit = c.committed ? `committed ${c.sha} on local branch ${c.branch} (never push it)` : `NOT committed — ${c.reason}`;
  }
  say(commit);

  const devVars = join(WORKER_DIR, '.dev.vars');
  const url = existsSync(devVars) ? parseDevVars(readFileSync(devVars, 'utf8')).BETTER_AUTH_URL : undefined;
  const repo = flags.repo ? resolve(flags.repo) : undefined;
  return finishUp({ url, repo, flags, plan }).then((extra) => probe({ url, token: flags['no-probe'] ? '' : findToken(repo), kind: plan.kind, target: plan.target, field: plan.field, models: plan.models }).then((p) => {
    for (const l of p.lines) say(l);
    say(p.ok === false ? 'FAILED the check above — the admin does not behave as declared; do not report it done.' : `done${p.ok ? '' : ' (not fully checked — see above)'}.`);
    for (const l of usage(url, plan.models, plan, flags.repo, !p.listed && !extra.widened, extra)) console.log(`  ${l}`);
    return p.ok === false ? 1 : 0;
  }));
}

/** Widen the agent's token to a new entity and mint the owner's sign-in link (each best effort, local admin only). */
async function finishUp({ url, repo, flags, plan }) {
  const extra = {};
  if (!url) return extra;
  const query = d1Query('local');
  if (plan.kind === 'entity' && repo && !flags.check) {
    const w = await widenToken({ repo, url, models: plan.models, entity: plan.target.name, query });
    if (w.state === 'widened' || w.state === 'skipped') extra.widened = w.line;
  }
  try {
    const vars = parseDevVars(readFileSync(join(WORKER_DIR, '.dev.vars'), 'utf8'));
    const link = newLink({ origin: url, email: (vars.ADMIN_EMAILS ?? '').split(',')[0] });
    await query(link.sql);
    extra.login = link.url;
  } catch { /* the link is a convenience: npm run login-link makes one */ }
  return extra;
}

try {
  process.exitCode = await main();
} catch (e) {
  if (!(e instanceof UsageError)) {
    console.error(`model: ${e instanceof Error ? e.message : e}`);
    process.exit(1);
  }
  console.error(`model: ${e.message}`);
  process.exit(2);
}
