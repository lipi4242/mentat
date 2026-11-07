// Whole-database JSON export and restore — the "no lock-in" promise: every
// row this admin holds can leave as plain JSON and come back into a fresh
// instance. Pure logic, no I/O: the caller passes `queryMany(sqls) → rows[][]`
// (wrangler d1 execute in scripts/, better-sqlite3 in the tests), so the same
// code is tested that the CLI runs.

export const FORMAT = 'mentat-admin-export';
export const VERSION = 1;

// Not data: sessions and OTP codes are short-lived credentials, and a restore
// that brought them back would resurrect logins on another instance. The
// user rows (auth_user, auth_account) and the agent token hashes DO travel.
export const SKIPPED = ['auth_session', 'auth_verification', 'auth_rate_limit'];

// SQLite's own and D1's bookkeeping tables; a target instance builds its own.
const INTERNAL = /^(sqlite_|_cf_|d1_migrations$)/;
export const isInternal = (t) => INTERNAL.test(t);

/** A table name as a SQL identifier. Names come from sqlite_master, but quote anyway. */
export const ident = (name) => `"${String(name).replace(/"/g, '""')}"`;
const str = (s) => `'${String(s).replace(/'/g, "''")}'`;

/** A JSON scalar as a SQL literal. Anything else is refused, never guessed. */
export function literal(v) {
  if (v === null || v === undefined) return 'NULL';
  if (typeof v === 'boolean') return v ? '1' : '0';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) throw new Error(`cannot restore a non-finite number: ${v}`);
    return String(v);
  }
  if (typeof v === 'string') return str(v);
  throw new Error(`cannot restore a non-scalar value: ${JSON.stringify(v)}`);
}

/** Parents before children, so a restore never inserts a dangling reference. */
export function dependencyOrder(tables, parentsOf) {
  const order = [];
  const state = new Map();
  const visit = (t) => {
    if (state.get(t) === 'done') return;
    if (state.get(t) === 'active') return; // a cycle: defer_foreign_keys covers it
    state.set(t, 'active');
    for (const p of parentsOf[t] ?? []) if (tables.includes(p) && p !== t) visit(p);
    state.set(t, 'done');
    order.push(t);
  };
  for (const t of [...tables].sort()) visit(t);
  return order;
}

/** Every user table, minus the bookkeeping ones. */
export async function listTables(queryMany) {
  const [rows] = await queryMany([`SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name`]);
  return rows.map((r) => r.name);
}

/**
 * Build the export. `only` narrows it to named tables (e.g. one plugin's);
 * a name that does not exist is an error, not an empty section.
 */
export async function exportDb(queryMany, { only, now = new Date() } = {}) {
  const all = await listTables(queryMany);
  const data = all.filter((t) => !INTERNAL.test(t));
  if (only) {
    const missing = only.filter((t) => !data.includes(t));
    if (missing.length) throw new Error(`no such table(s): ${missing.join(', ')}`);
  }
  const wanted = only ? [...only] : data.filter((t) => !SKIPPED.includes(t));
  const hasMigrations = all.includes('d1_migrations');
  const sqls = [
    ...wanted.map((t) => `SELECT "table" AS parent FROM pragma_foreign_key_list(${str(t)})`),
    ...wanted.map((t) => `SELECT * FROM ${ident(t)} ORDER BY rowid`),
    ...(hasMigrations ? ['SELECT name FROM d1_migrations ORDER BY id'] : []),
  ];
  const results = await queryMany(sqls);
  const parentsOf = {};
  wanted.forEach((t, i) => (parentsOf[t] = results[i].map((r) => r.parent)));
  const order = dependencyOrder(wanted, parentsOf);
  const tables = {};
  wanted.forEach((t, i) => (tables[t] = results[wanted.length + i]));
  return {
    format: FORMAT,
    version: VERSION,
    exported_at: now.toISOString(),
    migrations: hasMigrations ? results[2 * wanted.length].map((r) => r.name) : [],
    skipped: only ? [] : SKIPPED.filter((t) => data.includes(t)),
    order,
    tables,
  };
}

/** Shape check before anything is written. Returns the tables to restore, in order. */
export function planRestore(dump, { only } = {}) {
  if (!dump || dump.format !== FORMAT) throw new Error(`not a ${FORMAT} file`);
  if (dump.version !== VERSION) throw new Error(`unsupported export version ${dump.version} (this build reads ${VERSION})`);
  const order = (dump.order ?? []).filter((t) => (only ? only.includes(t) : true));
  if (only) {
    const missing = only.filter((t) => !order.includes(t));
    if (missing.length) throw new Error(`not in this export: ${missing.join(', ')}`);
  }
  return order;
}

/**
 * Refuse to restore over existing rows or into a table the target lacks.
 * Restore fills a freshly migrated instance; merging into live data is a
 * different operation and is deliberately not offered.
 */
export async function assertRestorable(queryMany, tables) {
  const present = await listTables(queryMany);
  const missing = tables.filter((t) => !present.includes(t));
  if (missing.length) {
    throw new Error(`target has no table(s) ${missing.join(', ')} — run the migrations first, or narrow with --tables`);
  }
  const counts = await queryMany(tables.map((t) => `SELECT count(*) AS n FROM ${ident(t)}`));
  const busy = tables.filter((t, i) => counts[i][0].n > 0);
  if (busy.length) throw new Error(`target table(s) not empty: ${busy.join(', ')} — restore only fills a fresh instance`);
}

/** The restore as one SQL script: foreign keys checked at commit, parents first. */
export function restoreSql(dump, tables) {
  const lines = ['PRAGMA defer_foreign_keys = on;'];
  for (const t of tables) {
    for (const row of dump.tables[t] ?? []) {
      const cols = Object.keys(row);
      lines.push(
        `INSERT INTO ${ident(t)} (${cols.map(ident).join(', ')}) VALUES (${cols.map((c) => literal(row[c])).join(', ')});`,
      );
    }
  }
  return lines.join('\n') + '\n';
}
