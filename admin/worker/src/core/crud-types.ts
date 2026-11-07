import type { Context } from 'hono';
import type { AppEnv } from '../types';

export type CrudSpec = {
  /** URL segment, e.g. 'cases' → /api/cases */
  path: string;
  /** SQL table name, quoted by the caller if it is a keyword (e.g. '"case"') */
  table: string;
  /** Writable columns. Anything not listed is dropped from request bodies. */
  columns: string[];
  /** Scope required for writes (POST/PATCH) on this resource. */
  scope: string;
  /** Scope required for reads (GET). Defaults to `scope` — set this to unlock
   *  a `:read`-only token for a resource whose writers need more. */
  readScope?: string | string[];
  /** Field checks (types, bounds, patterns) on the allowlisted body: a 400 message naming the field, or null. */
  validate?: (body: Record<string, unknown>, mode: 'create' | 'update') => string | null;
  /** Columns the list filters on by equality (`GET /api/x?col=value`); values are bound. */
  filterable?: string[];
  /**
   * Ordering clause appended to the list query. Developer-supplied only —
   * never built from request input.
   */
  orderBy?: string;
  /**
   * WHERE-clause fragment appended to the list query, same trust level as
   * `orderBy` (developer-supplied SQL, never end-user data). Use it to
   * exclude soft-deleted/archived rows from the default listing.
   */
  where?: string;
  /**
   * Build (not run) the audit-trail insert for a write, so it commits
   * atomically with the row via `DB.batch([...])`. Omit to skip auditing.
   */
  eventStmt?: (c: Context<AppEnv>, id: string, action: 'created' | 'updated') => D1PreparedStatement;
  /** Extra data merged into the GET /:id response (e.g. a case's event trail).
   *  The stored row always wins over this on key collision. */
  detail?: (c: Context<AppEnv>, id: string) => Promise<Record<string, unknown>>;
  /**
   * Stamp `updated_at = datetime('now')` on every PATCH that changes at least
   * one allowlisted column. Defaults to true — `updated_at` has an insert-only
   * default (migrations/0002_core.sql), so without this a PATCH silently
   * leaves it stale. Set to false for tables with no `updated_at` column.
   */
  touchUpdatedAt?: boolean;
  /**
   * NOT NULL columns (with no SQL default) that must be present in a POST
   * body. Checked after `pick`, so a key outside `columns` can never satisfy
   * it. Deliberately POST-only — a PATCH body is legitimately partial, so
   * `required` is never applied there.
   */
  required?: string[];
  /**
   * Allowlisted columns that are NOT NULL in the schema. An explicit `null`
   * for one of these is rejected with a 400 naming the column, on POST and
   * PATCH alike.
   *
   * Distinct from `required`, which only asks whether a key is *present* on a
   * POST. This is about the value: the edit form deliberately sends `null` for
   * a field the user blanked (omitting it would read as "unchanged"), and
   * PATCH skips `required` because a partial body is legitimate — so without
   * this, clearing a NOT NULL field on an edit form reached SQLite as a
   * constraint violation and surfaced as a 500 telling the user to try again
   * later, which could never work.
   *
   * Populate it from the migrations, not from a field list. Every column here
   * must also be in `columns` — enforced by `assertValidSpec`.
   */
  notNull?: string[];
  /**
   * When set, POST becomes an upsert keyed on this UNIQUE constraint instead
   * of erroring on conflict: `ON CONFLICT(...) DO UPDATE SET` for every
   * other allowlisted column present in the body. Built for `offer`, where
   * `UNIQUE(supplier_id, product_id)` makes it the current price observation
   * rather than a log — re-checking a price is a legitimate repeat POST, and
   * a plain INSERT would opaquely 500 on the UNIQUE violation.
   *
   * Two constraints, both enforced at registration time by `assertValidSpec`
   * (called from `registerCrud`):
   *  - incompatible with `eventStmt` — the event is built with the freshly
   *    minted id before the batch runs, so on a genuine conflict the audit
   *    row would name an id no row has;
   *  - every column here must also be in `required`, or the conflict
   *    follow-up SELECT can bind `undefined` for a column the body omitted.
   */
  conflictColumns?: string[];
};

// SQL words that can appear in a `where` fragment without naming a column.
const SQL_WORDS = new Set([
  'and', 'or', 'not', 'null', 'is', 'in', 'like', 'between', 'exists', 'case', 'when', 'then',
  'else', 'end', 'true', 'false', 'cast', 'as', 'coalesce',
]);

/**
 * Bare identifiers referenced by a `where` fragment, minus SQL words, string
 * literals and numbers. `where` is developer-supplied SQL, so this is a
 * best-effort read of a short hand-written clause, not a SQL parser.
 */
function whereColumns(where: string): string[] {
  const withoutLiterals = where.replace(/'[^']*'/g, ' ').replace(/"[^"]*"/g, ' ');
  const words = withoutLiterals.match(/[A-Za-z_][A-Za-z0-9_]*/g) ?? [];
  return [...new Set(words.filter((w) => !SQL_WORDS.has(w.toLowerCase())))];
}

/**
 * Fail loudly at registration time, not in production, on the `conflictColumns`
 * invariants documented above plus one more: a column the list query *filters*
 * on must also be writable.
 *
 * That last one is not a style rule. `"case"` filtered on `archived = 0` while
 * omitting `archived` from `columns`, so `PATCH {archived: 1}` dropped the key
 * in `pick()` and answered 200 without touching the row — archiving a case was
 * a silent no-op, and the UI reported success. A filter you cannot write is a
 * row state you can never reach.
 *
 * If a future spec genuinely wants to filter on a read-only column, that is a
 * deliberate change to make here — not something to slip past by adding the
 * column to `columns`.
 */
export function assertValidSpec(spec: CrudSpec): void {
  if (spec.where) {
    const unwritable = whereColumns(spec.where).filter((k) => !spec.columns.includes(k));
    if (unwritable.length) {
      throw new Error(
        `registerCrud(${spec.path}): where filters on column(s) that are not writable: ${unwritable.join(', ')}`,
      );
    }
  }
  const unknownNotNull = (spec.notNull ?? []).filter((k) => !spec.columns.includes(k));
  if (unknownNotNull.length) {
    throw new Error(
      `registerCrud(${spec.path}): notNull names column(s) that are not writable: ${unknownNotNull.join(', ')}`,
    );
  }
  if (!spec.conflictColumns?.length) return;
  if (spec.eventStmt) {
    throw new Error(`registerCrud(${spec.path}): conflictColumns cannot be combined with eventStmt`);
  }
  const notRequired = spec.conflictColumns.filter((k) => !spec.required?.includes(k));
  if (notRequired.length) {
    throw new Error(
      `registerCrud(${spec.path}): conflictColumns must all be in required (missing: ${notRequired.join(', ')})`,
    );
  }
}
