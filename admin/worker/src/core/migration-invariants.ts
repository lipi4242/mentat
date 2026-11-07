// Pure rules for the migration-band invariants. Kept data-in/data-out (no
// filesystem access) so the cross-plugin rule can be exercised against a
// synthetic fixture, not only against however many plugins the real config
// happens to hold today.

export type MigrationFile = { name: string; sql: string };
/** `extends`: other plugins' tables this one may add columns to (the custom plugin, config/models.json). */
export type PluginBand = { id: string; migrationBand: [number, number]; tables: string[]; extends?: string[] };

export const numberOf = (name: string): number => {
  const n = Number(name.slice(0, 4));
  // A badly-named file returning NaN would silently fall outside every band
  // check rather than failing it — the opposite of what a band invariant is
  // for. Fail loudly instead of letting it slip through uncounted.
  if (!Number.isFinite(n)) throw new Error(`migration file has no valid 4-digit id: ${name}`);
  return n;
};

// Strip line comments, block comments, and the contents of string literals
// before matching — otherwise a mention in a comment ("-- see supplier for
// details") or a string literal ("'the supplier said no'") reads as a real
// reference.
const strip = (sql: string) =>
  sql
    .replace(/--[^\n]*/g, ' ')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/'(?:[^']|'')*'/g, "''");

// A declared table name is interpolated into a RegExp, so it must be escaped
// first — an unescaped metacharacter either crashes the check (a name like
// "b(table") or silently corrupts the match (a name like "b|table").
const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Match on identifier boundaries, tolerant of quoting and of whitespace
// (including newlines/tabs) around the name — multi-line FK formatting is
// the norm in this schema. Without boundaries, `supplier_id` reads as a
// reference to table `supplier`, and `product_v2` as `product`.
const referencesTable = (strippedSql: string, table: string): boolean => {
  const re = new RegExp(`(?<![A-Za-z0-9_])"?${escapeRegExp(table)}"?(?![A-Za-z0-9_])`, 'i');
  return re.test(strippedSql);
};

/** Returns one human-readable violation string per offending reference; empty when clean. */
export function crossPluginViolations(files: MigrationFile[], plugins: PluginBand[]): string[] {
  const violations: string[] = [];
  for (const plugin of plugins) {
    const [lo, hi] = plugin.migrationBand;
    const others = plugins
      .filter((p) => p.id !== plugin.id)
      .flatMap((p) => p.tables)
      .filter((t) => !plugin.extends?.includes(t));
    const owned = files.filter((f) => {
      const n = numberOf(f.name);
      return n >= lo && n <= hi;
    });
    for (const f of owned) {
      const stripped = strip(f.sql);
      for (const t of others) {
        if (referencesTable(stripped, t)) {
          violations.push(`${f.name} references ${t}, owned by another plugin`);
        }
      }
    }
  }
  return violations;
}
