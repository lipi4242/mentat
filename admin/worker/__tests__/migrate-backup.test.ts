// A migration is the one irreversible step (0101 drops the retired purchasing
// tables), so `npm run migrate:*` must take a restorable export first, and
// stop if that export fails. `&&` is the stop: with `;` a failed backup would
// still run the migration.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pkg = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'package.json'), 'utf8'));

describe('npm run migrate:*', () => {
  it.each(['local', 'remote'])('backs up the %s database before applying migrations', (target) => {
    const script: string = pkg.scripts[`migrate:${target}`];
    const backup = script.indexOf(`node scripts/export.mjs --${target} --backup &&`);
    const apply = script.indexOf(`wrangler d1 migrations apply DB --${target}`);
    expect(backup, script).toBeGreaterThanOrEqual(0);
    expect(apply).toBeGreaterThan(backup);
  });
});
