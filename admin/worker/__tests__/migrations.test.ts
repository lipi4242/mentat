import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PLUGINS, CORE_BAND, RETIRED_BANDS } from '../../config/plugins';
import { numberOf, crossPluginViolations, type MigrationFile, type PluginBand } from '../src/core/migration-invariants';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'migrations');
const fileNames = readdirSync(DIR).filter((f) => f.endsWith('.sql')).sort();
const files: MigrationFile[] = fileNames.map((name) => ({ name, sql: readFileSync(join(DIR, name), 'utf8') }));

describe('migration bands', () => {
  it('has no duplicate ids', () => {
    const ids = fileNames.map(numberOf);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('places every migration inside a declared band', () => {
    const bands: Array<[number, number]> = [
      CORE_BAND,
      ...PLUGINS.map((p) => p.migrationBand),
      ...RETIRED_BANDS.map((p) => p.migrationBand),
    ];
    for (const f of fileNames) {
      const n = numberOf(f);
      const inSome = bands.some(([lo, hi]) => n >= lo && n <= hi);
      expect(inSome, `${f} (${n}) is outside every declared band`).toBe(true);
    }
  });

  // The real-config arm below is only as strong as the number of registered
  // plugins: with a single plugin, "other plugins' tables" is always empty
  // and the loop never runs, so a green result here proves nothing on its
  // own. The synthetic-fixture suite is what keeps the rule provably alive;
  // this arm just wires the same proven function to production data so a
  // future second plugin gets checked automatically.
  it('does not let a plugin migration touch another plugin table (real config)', () => {
    const violations = crossPluginViolations(files, [...PLUGINS, ...RETIRED_BANDS]);
    expect(violations, violations.join('; ')).toEqual([]);
  });

  // A retired band stays reserved: a new plugin landing on its numbers would
  // share migration ids with tables that were dropped.
  it('keeps retired bands disjoint from live plugin bands', () => {
    for (const r of RETIRED_BANDS) {
      for (const p of PLUGINS) {
        const overlap = p.migrationBand[0] <= r.migrationBand[1] && r.migrationBand[0] <= p.migrationBand[1];
        expect(overlap, `${p.id} overlaps retired ${r.id}`).toBe(false);
      }
    }
  });
});

describe('crossPluginViolations (synthetic fixture)', () => {
  const pluginA: PluginBand = { id: 'a', migrationBand: [100, 199], tables: ['a_table'] };
  const pluginB: PluginBand = { id: 'b', migrationBand: [200, 299], tables: ['b_table'] };

  // Wraps a snippet inside plugin A's migration; plugin B's migration stays
  // fixed. `snippet` stands in for however a real reference to b_table might
  // be written. `sep` is the separator before the snippet — defaults to a
  // newline (the common case in this schema's multi-line FK formatting), but
  // is overridable so a near-miss case can be tested with a plain space,
  // which is the separator the old substring matcher actually handled.
  const filesWith = (snippet: string, sep = '\n'): MigrationFile[] => [
    { name: '0100_a.sql', sql: `CREATE TABLE a_table (id TEXT);${sep}${snippet}` },
    { name: '0200_b.sql', sql: 'CREATE TABLE b_table (id TEXT);' },
  ];

  it('lets a plugin touch exactly the tables it declares it extends', () => {
    const alter = 'ALTER TABLE b_table ADD COLUMN x TEXT;';
    expect(crossPluginViolations(filesWith(alter), [{ ...pluginA, extends: ['b_table'] }, pluginB])).toEqual([]);
    expect(crossPluginViolations(filesWith(alter), [pluginA, pluginB])).toEqual(['0100_a.sql references b_table, owned by another plugin']);
  });

  it('reports nothing for a clean pair', () => {
    expect(crossPluginViolations(filesWith(''), [pluginA, pluginB])).toEqual([]);
  });

  // Each of these is a real reference, just formatted differently. Multi-line
  // FK wrapping (newline/tab before the table name) is the norm in this
  // repo's own migrations, so it is the one most likely to hide a real
  // violation if the matcher only handles a single leading space.
  it.each([
    ['newline before the table name', 'REFERENCES\nb_table(id)'],
    ['tab before the table name', 'REFERENCES\tb_table(id)'],
    ['no space, wrapped in parens', 'JOIN(b_table)'],
    ['comma-separated FROM list', 'FROM a_table,b_table'],
    ['double-quoted identifier', 'REFERENCES "b_table"(id)'],
    ['table name at line start', '\nb_table\n'],
  ])('catches a reference written as: %s', (_label, snippet) => {
    const violations = crossPluginViolations(filesWith(snippet), [pluginA, pluginB]);
    expect(violations).toEqual(['0100_a.sql references b_table, owned by another plugin']);
  });

  // None of these are references to b_table at all — a naive substring or
  // loose-boundary match would flag them anyway. The first case uses a plain
  // space separator (rather than the default newline) deliberately: a
  // newline here would make the case pass for the wrong reason — the old
  // `sql.includes(' ' + t)` matcher only ever handled a leading space, so a
  // newline-separated snippet passes under both the old and new matcher and
  // proves nothing about identifier boundaries specifically.
  it.each([
    ['a column merely prefixed by the table name', 'b_table_id TEXT', ' '],
    ['a differently-suffixed table name', 'CREATE TABLE b_table_v2 (id TEXT);', '\n'],
    ['a line comment mentioning the table', '-- see b_table for details', '\n'],
    ['a string literal mentioning the table', "notes TEXT DEFAULT 'the b_table said no'", '\n'],
  ])('does not flag a near-miss: %s', (_label, snippet, sep) => {
    expect(crossPluginViolations(filesWith(snippet, sep), [pluginA, pluginB])).toEqual([]);
  });

  // The declared table name is interpolated into a RegExp; an unescaped
  // metacharacter in it must not crash the check or corrupt the match.
  it('does not crash or misbehave when a table name contains a regex metacharacter', () => {
    const weird: PluginBand = { id: 'weird', migrationBand: [300, 399], tables: ['b(table'] };
    const dirty: MigrationFile[] = [
      { name: '0100_a.sql', sql: 'CREATE TABLE a_table (id TEXT);\nREFERENCES b(table(id)' },
      { name: '0300_weird.sql', sql: 'CREATE TABLE "b(table" (id TEXT);' },
    ];
    expect(() => crossPluginViolations(dirty, [pluginA, weird])).not.toThrow();
    expect(crossPluginViolations(dirty, [pluginA, weird])).toEqual([
      '0100_a.sql references b(table, owned by another plugin',
    ]);
  });
});
