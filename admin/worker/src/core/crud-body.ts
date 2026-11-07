import type { Context } from 'hono';
import type { AppEnv } from '../types';

/**
 * SQLite (and D1) has no boolean bind type — `true`/`false` throw at bind
 * time ("can only bind numbers, strings, bigints, buffers, null"). JSON's
 * only spelling of a boolean is `true`/`false` though, and it is the natural
 * value for an INTEGER-as-boolean column like `offer.in_stock`. Coerce to
 * SQLite's own 0/1 convention instead of rejecting — rejecting a boolean
 * here would be the exact defect class `invalidBody`'s scalar guard exists
 * to close, just moved one column over.
 *
 * `pick()` carries no per-column type information, so this applies to every
 * column, not just the INTEGER-as-boolean ones — `POST /api/suppliers
 * {"name": true}` now stores the string `"1"` instead of 500ing. Still
 * nonsense input, just quiet nonsense instead of loud nonsense. Accepted:
 * adding a `booleanColumns?: string[]` allowlist to `CrudSpec` to scope this
 * per-table was judged more registration surface than the problem is worth.
 */
function coerce(v: unknown): unknown {
  return typeof v === 'boolean' ? (v ? 1 : 0) : v;
}

/** Keep only the allowlisted keys present on the body, in allowlist order. */
export function pick(body: Record<string, unknown>, columns: string[]): [string[], unknown[]] {
  const keys = columns.filter((k) => Object.prototype.hasOwnProperty.call(body, k));
  return [keys, keys.map((k) => coerce(body[k]))];
}

/**
 * Parse the request body as JSON and require a plain object. Malformed JSON,
 * a missing body, `null`, an array, or a bare scalar all return null here
 * instead of reaching `pick()` — `Object.prototype.hasOwnProperty.call(null, k)`
 * throws, so without this every one of those shapes was a 500.
 */
export async function readBody(c: Context<AppEnv>): Promise<Record<string, unknown> | null> {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return null;
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return null;
  return body as Record<string, unknown>;
}

/**
 * Validates a body already reduced to allowlisted columns by `pick()`. Two
 * independent checks, both there to keep a client mistake looking like a
 * 400 instead of an internal error:
 *  - `required` catches a missing NOT NULL column before it reaches SQLite
 *    as a constraint violation (`POST /api/cases {}` was a 500 without this).
 *  - the scalar guard rejects an object/array value before it reaches
 *    SQLite as a bind parameter (D1 throws on non-scalar binds).
 * `required` is meant for POST only — PATCH bodies are legitimately partial,
 * so callers pass it there. `notNull` applies to both: it is about the value
 * sent, not about which keys the body carries, and an explicit null on a NOT
 * NULL column is a client mistake either way.
 */
export function invalidBody(
  keys: string[],
  values: unknown[],
  required?: string[],
  notNull?: string[],
): { error: string } | null {
  if (required?.length) {
    const missing = required.filter((k) => !keys.includes(k));
    if (missing.length) return { error: `missing required field(s): ${missing.join(', ')}` };
  }
  if (notNull?.length) {
    const nulled = keys.filter((k, i) => values[i] === null && notNull.includes(k));
    if (nulled.length) return { error: `must not be empty: ${nulled.join(', ')}` };
  }
  const nonScalar = keys.filter((k, i) => {
    const v = values[i];
    return v !== null && typeof v === 'object';
  });
  if (nonScalar.length) return { error: `must be a scalar value: ${nonScalar.join(', ')}` };
  return null;
}
