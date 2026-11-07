#!/usr/bin/env node
// Seed the todo principals (humans and agents) of an instance from JSON.
//
//   npm run instance:seed-principals -- --file principals.json --local|--remote [--dry-run]
//
// File shape and rules: scripts/lib/seed-principals.mjs. Rerunning is safe:
// what is already there is left alone. --remote uses the instance file that
// config/instance.mjs finds (MENTAT_ADMIN_INSTANCE=~/.config/mentat-admin/<slug>.json).
import { readFileSync } from 'node:fs';
import { d1Query, flag, parseTarget } from './lib/d1.mjs';
import { parseSeed, seedPrincipals } from './lib/seed-principals.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
const file = flag(argv, '--file');
if (!target || !file) {
  console.error('usage: npm run instance:seed-principals -- --file <json> --local|--remote [--dry-run]');
  process.exit(1);
}

try {
  const entries = parseSeed(JSON.parse(readFileSync(file, 'utf8')));
  if (argv.includes('--dry-run')) {
    const { sql } = await seedPrincipals(null, entries, { dryRun: true });
    console.log(`[dry-run] would execute on the ${target} database:\n\n${sql.join(';\n')}\n\n[dry-run] nothing was written.`);
    process.exit(0);
  }
  const { report } = await seedPrincipals(d1Query(target), entries);
  for (const r of report) {
    const who = r.entry.kind === 'human' ? r.entry.email : `agent "${r.entry.label}"`;
    console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${who} (@${r.entry.handle}): ${r.status}`);
  }
  if (report.some((r) => !r.ok)) process.exit(1);
} catch (err) {
  console.error(`seed-principals: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
