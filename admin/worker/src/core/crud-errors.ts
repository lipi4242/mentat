import type { Env } from '../types';

/**
 * True for a SQLite/D1 FOREIGN KEY constraint failure — a caller referencing
 * a row that does not (or no longer) exist, which is a client mistake, not a
 * bug in this API.
 */
export function isForeignKeyError(err: unknown): boolean {
  return err instanceof Error && /FOREIGN KEY constraint failed/i.test(err.message);
}

/** A client mistake, shaped for `c.json(body, status)`. */
export type WriteError = { error: string; status: 400 | 409 };

/**
 * Maps the three SQLite constraint failures that are caller mistakes onto a
 * status. Anything else is ours and must keep reaching `onError` as a 500.
 *
 * The SPA's dropdowns cannot send a value a CHECK rejects, but an agent
 * calling the API directly can. `HTTP 500 —
 * {"error":"internal error"}` names nothing, so a wrong guess is unfixable
 * from the caller's side; a 400 that says which column refused the value is.
 *
 * What is surfaced is deliberately just the constraint's own tail — SQLite
 * reports `NOT NULL constraint failed: case.title` and `CHECK constraint
 * failed: <table-or-constraint-name>`, never the row's values or the clause's
 * text — so this identifies the offending column without echoing schema
 * internals or the caller's data back at them.
 */
export function writeError(err: unknown): WriteError | null {
  if (!(err instanceof Error)) return null;
  if (isForeignKeyError(err)) return { error: 'references a row that does not exist', status: 409 };

  const notNull = /NOT NULL constraint failed:\s*(\S+)/i.exec(err.message);
  // `table.column` — the column alone is what the caller sent.
  if (notNull) return { error: `must not be empty: ${notNull[1].split('.').pop()}`, status: 400 };

  const check = /CHECK constraint failed:\s*(\S+)/i.exec(err.message);
  if (check) return { error: `value rejected by a database rule: ${check[1]}`, status: 400 };

  return null;
}

/**
 * Runs a `DB.batch()`, mapping the caller-mistake constraint failures above
 * to a 4xx-shaped result instead of letting them reach the generic `onError`
 * handler as a 500. Any other failure re-throws — this narrows only the error
 * classes that are a client mistake, not ours. Shared by `registerCrud`'s
 * POST and PATCH so all nine registrations get it from one place.
 */
export async function batchOrConflict(DB: Env['DB'], stmts: D1PreparedStatement[]): Promise<WriteError | null> {
  try {
    await DB.batch(stmts);
    return null;
  } catch (err) {
    const mapped = writeError(err);
    if (mapped) return mapped;
    throw err;
  }
}
