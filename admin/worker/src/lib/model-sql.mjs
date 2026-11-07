// config/models.json → the SQL that makes the schema match it. Shared by the
// migration generator (scripts/model-migration.mjs) and the tests. Plain JS on
// purpose: the generator runs on a bare Node, like token-rules.mjs.
//
// Additive only: a missing table is created, a missing column added. Nothing
// is renamed, retyped or dropped — that is a hand-written migration and a
// human's decision.

/** models.fields key → the plugin table it extends. */
export const EXTENSIBLE_TABLES = { cases: 'cases_case' };

const SQL_TYPE = {
  text: 'TEXT', textarea: 'TEXT', email: 'TEXT', date: 'TEXT', select: 'TEXT', ref: 'TEXT',
  number: 'REAL', integer: 'INTEGER', checkbox: 'INTEGER',
};

function columnSql(f, { notNull }) {
  let sql = `${f.name} ${SQL_TYPE[f.type]}`;
  if (notNull && f.required) sql += ' NOT NULL';
  if (f.type === 'ref') sql += ` REFERENCES custom_${f.ref}(id)`;
  return sql;
}

const refIndex = (table, f) => (f.type === 'ref' ? [`CREATE INDEX IF NOT EXISTS idx_${table}_${f.name} ON ${table} (${f.name});`] : []);

/**
 * Statements that bring `schema` ({table: Set<column>}) up to `models`.
 * A column added to an existing table is never NOT NULL: the rows already
 * there have no value (the API still requires it on create).
 */
export function modelSql(models, schema) {
  const out = [];
  for (const [key, fields] of Object.entries(models.fields ?? {})) {
    const table = EXTENSIBLE_TABLES[key];
    for (const f of fields) {
      if (!schema[table]?.has(f.name)) out.push(`ALTER TABLE ${table} ADD COLUMN ${columnSql(f, { notNull: false })};`, ...refIndex(table, f));
    }
  }
  for (const e of models.entities ?? []) {
    const table = `custom_${e.name}`;
    if (!schema[table]) {
      const cols = [
        'id TEXT PRIMARY KEY NOT NULL',
        ...e.fields.map((f) => columnSql(f, { notNull: true })),
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))",
        "updated_at TEXT NOT NULL DEFAULT (datetime('now'))",
      ];
      out.push(`CREATE TABLE ${table} (\n  ${cols.join(',\n  ')}\n);`, ...e.fields.flatMap((f) => refIndex(table, f)));
      continue;
    }
    for (const f of e.fields) {
      if (!schema[table].has(f.name)) out.push(`ALTER TABLE ${table} ADD COLUMN ${columnSql(f, { notNull: false })};`, ...refIndex(table, f));
    }
  }
  return out;
}

/** {table: Set<column>} of a better-sqlite3 database. */
export function schemaOf(db) {
  const out = {};
  for (const { name } of db.prepare(`SELECT name FROM sqlite_master WHERE type = 'table'`).all()) {
    out[name] = new Set(db.prepare(`SELECT name FROM pragma_table_info(?)`).all(name).map((c) => c.name));
  }
  return out;
}
