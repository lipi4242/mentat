import type { Context } from 'hono';
import type { AppEnv } from '../types';
import type { CrudSpec } from './crud-types';
import { batchOrConflict, type WriteError } from './crud-errors';

/**
 * Builds and runs a POST's INSERT (or, when `conflictColumns` is set, an
 * upsert), paired atomically with the spec's `eventStmt` via `DB.batch()`.
 * Returns the id of the row that now exists — the freshly minted one on a
 * plain insert, or the pre-existing row's id when a conflict upserted it in
 * place. Split out of `registerCrud` to keep that file under the 150-line
 * guideline; this is the one part of POST with enough branching (plain
 * insert vs. upsert, plus the conflict-key follow-up read) to earn its own
 * file.
 */
export async function insertRow(
  c: Context<AppEnv>,
  spec: CrudSpec,
  keys: string[],
  values: unknown[],
  body: Record<string, unknown>,
): Promise<{ id: string } | WriteError> {
  // Ids are always minted server-side — there is nothing in this project
  // that needs a caller-chosen id, and accepting one bypasses the allowlist
  // undocumented, lets `{"id":""}` create an unreachable row, lets
  // `{"id":12345}` get coerced to a string, and turns a duplicate id into a
  // 500 that works as an existence oracle. Do not re-add a body-supplied id.
  const id = crypto.randomUUID();
  const cols = ['id', ...keys];
  const placeholders = cols.map((_, i) => `?${i + 1}`).join(', ');
  let insertSql = `INSERT INTO ${spec.table} (${cols.join(', ')}) VALUES (${placeholders})`;
  if (spec.conflictColumns?.length) {
    const updateCols = keys.filter((k) => !spec.conflictColumns!.includes(k));
    // `id = id` is a harmless self-assignment that keeps this clause
    // non-empty (SQLite requires at least one SET) even when the body
    // carries only the conflict-key columns, and it also keeps this branch
    // as DO UPDATE rather than DO NOTHING so exactly one row always exists
    // to look up afterwards.
    const updateSet = ['id = id', ...updateCols.map((k) => `${k} = excluded.${k}`)].join(', ');
    insertSql += ` ON CONFLICT(${spec.conflictColumns.join(', ')}) DO UPDATE SET ${updateSet}`;
  }
  const insertStmt = c.env.DB.prepare(insertSql).bind(id, ...values);
  const ev = spec.eventStmt?.(c, id, 'created');
  // Row + event commit together: D1's batch() is an implicit transaction, so
  // a failing event insert leaves no orphaned, unaudited row behind. A
  // FOREIGN KEY failure (a caller-supplied id that names no row) is mapped
  // to a 409-shaped result here instead of surfacing as a 500.
  const conflict = await batchOrConflict(c.env.DB, ev ? [insertStmt, ev] : [insertStmt]);
  if (conflict) return conflict;
  if (!spec.conflictColumns?.length) return { id };
  // On conflict, the freshly minted `id` lost — the row's real id is
  // whatever it already was. A follow-up read by the conflict key is simpler
  // and more portable than relying on `RETURNING` surviving `DB.batch()`,
  // which the D1 test emulator does not reproduce.
  const conflictWhere = spec.conflictColumns.map((k, i) => `${k} = ?${i + 1}`).join(' AND ');
  const conflictValues = spec.conflictColumns.map((k) => body[k]);
  const row = await c.env.DB.prepare(`SELECT id FROM ${spec.table} WHERE ${conflictWhere}`)
    .bind(...conflictValues)
    .first<{ id: string }>();
  return { id: row?.id ?? id };
}
