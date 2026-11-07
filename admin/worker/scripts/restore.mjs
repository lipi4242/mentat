#!/usr/bin/env node
// Restore an export (scripts/export.mjs) into a freshly migrated database.
//
//   node scripts/restore.mjs --local|--remote --in FILE [--tables a,b] [--dry-run]
//
// Order: create the instance, `npm run migrate:local|remote`, then this.
// Every restored table must exist in the target and be empty — restore fills
// a fresh instance, it does not merge into live data. --tables narrows the
// restore (e.g. leave out a plugin whose tables this instance no longer has).
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { assertRestorable, planRestore, restoreSql } from './lib/dump.mjs';
import { d1ExecFile, d1Query, flag, parseTarget, tablesFlag } from './lib/d1.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
const input = flag(argv, '--in');
if (!target || !input) {
  console.error('usage: node scripts/restore.mjs --local|--remote --in FILE [--tables a,b] [--dry-run]');
  process.exit(1);
}

try {
  const dump = JSON.parse(readFileSync(input, 'utf8'));
  const tables = planRestore(dump, { only: tablesFlag(argv) });
  await assertRestorable(d1Query(target), tables);
  for (const t of tables) console.error(`restore: ${t} ← ${dump.tables[t].length} row(s)`);
  if (argv.includes('--dry-run')) {
    console.error('restore: dry run, nothing written');
    process.exit(0);
  }
  // The SQL carries the data, so it lives only as long as the call: a private
  // temp dir, removed whatever happens.
  const dir = mkdtempSync(join(tmpdir(), 'mentat-restore-'));
  try {
    const file = join(dir, 'restore.sql');
    writeFileSync(file, restoreSql(dump, tables), { mode: 0o600 });
    d1ExecFile(target, file);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  console.error(`restore: ${tables.length} table(s) restored into the ${target} database`);
} catch (err) {
  console.error(`restore: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
