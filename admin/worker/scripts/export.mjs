#!/usr/bin/env node
// Export the admin database as JSON (see scripts/lib/dump.mjs for the format).
//
//   node scripts/export.mjs --local|--remote [--out FILE] [--tables a,b]
//   node scripts/export.mjs --local|--remote --backup
//
// --out writes the file with mode 0600 (it holds the users' e-mail addresses
// and the agent token hashes); without it the JSON goes to stdout.
// --backup writes config/backups/<target>-<timestamp>.json
// (gitignored) and is what `npm run migrate:*` runs before every migration,
// so no schema change — dropping a plugin's tables included — happens
// without a restorable copy. An empty database (fresh clone) has nothing to
// back up and is skipped.
import { chmodSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { exportDb, isInternal, listTables } from './lib/dump.mjs';
import { ROOT, d1Query, flag, parseTarget, tablesFlag } from './lib/d1.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
if (!target) {
  console.error('usage: node scripts/export.mjs --local|--remote [--out FILE | --backup] [--tables a,b]');
  process.exit(1);
}

const query = d1Query(target);

function save(path, dump) {
  writeFileSync(path, JSON.stringify(dump, null, 2) + '\n', { mode: 0o600 });
  chmodSync(path, 0o600); // an existing file keeps its old mode otherwise
}

try {
  if (argv.includes('--backup')) {
    const data = (await listTables(query)).filter((t) => !isInternal(t));
    if (!data.length) {
      console.error(`export: ${target} database is empty — nothing to back up`);
      process.exit(0);
    }
    const dir = join(ROOT, 'config', 'backups');
    mkdirSync(dir, { recursive: true, mode: 0o700 });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const path = join(dir, `${target}-${stamp}.json`);
    save(path, await exportDb(query));
    console.error(`export: backup written to ${path}`);
  } else {
    const dump = await exportDb(query, { only: tablesFlag(argv) });
    const out = flag(argv, '--out');
    if (out) {
      save(out, dump);
      const rows = Object.values(dump.tables).reduce((n, t) => n + t.length, 0);
      console.error(`export: ${dump.order.length} table(s), ${rows} row(s) → ${out}`);
    } else {
      process.stdout.write(JSON.stringify(dump, null, 2) + '\n');
    }
  }
} catch (err) {
  console.error(`export: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
