import type { Hono } from 'hono';
import type { AppEnv } from '../types';
import { requireWriter } from '../lib/guards';
import { pick, readBody, invalidBody } from './crud-body';
import { insertRow } from './crud-write';
import { batchOrConflict } from './crud-errors';
import { assertValidSpec, type CrudSpec } from './crud-types';

export type { CrudSpec };

/** The spec's own field checks, on the allowlisted keys of the body only. */
function problem(spec: CrudSpec, body: Record<string, unknown>, mode: 'create' | 'update'): { error: string } | null {
  if (!spec.validate) return null;
  const msg = spec.validate(Object.fromEntries(spec.columns.filter((k) => k in body).map((k) => [k, body[k]])), mode);
  return msg ? { error: msg } : null;
}

/**
 * One declarative registration per table. Columns are an allowlist, so an
 * unexpected key in a request body can never become part of a statement —
 * values are always bound, never interpolated.
 *
 * Note on `X-Total-Count` / `SELECT *`: the list endpoint has no pagination,
 * so the header is a genuine full row count today — the moment a LIMIT is
 * added here it must change to a real count query. `SELECT *` also means the
 * shape of this API changes the moment a migration adds a column; that is
 * accepted for now, not an oversight.
 */
export function registerCrud(app: Hono<AppEnv>, spec: CrudSpec) {
  assertValidSpec(spec);
  const base = `/api/${spec.path}`;
  const touchUpdatedAt = spec.touchUpdatedAt ?? true;
  const readScope = spec.readScope ?? spec.scope;

  app.get(base, async (c) => {
    const denied = await requireWriter(c, readScope);
    if (denied) return denied;
    const filters = (spec.filterable ?? []).filter((k) => c.req.query(k) !== undefined);
    const conds = [...(spec.where ? [`(${spec.where})`] : []), ...filters.map((k, i) => `${k} = ?${i + 1}`)];
    const where = conds.length ? `WHERE ${conds.join(' AND ')}` : '';
    const { results } = await c.env.DB.prepare(
      `SELECT * FROM ${spec.table} ${where} ${spec.orderBy ? `ORDER BY ${spec.orderBy}` : ''}`,
    )
      .bind(...filters.map((k) => c.req.query(k)))
      .all();
    return c.json(results, 200, { 'X-Total-Count': String(results.length) });
  });

  app.get(`${base}/:id`, async (c) => {
    const denied = await requireWriter(c, readScope);
    if (denied) return denied;
    const id = c.req.param('id');
    const row = await c.env.DB.prepare(`SELECT * FROM ${spec.table} WHERE id = ?1`).bind(id).first();
    if (!row) return c.json({ error: 'not found' }, 404);
    const extra = spec.detail ? await spec.detail(c, id) : {};
    // The stored row always wins over a detail hook's output on key collision.
    return c.json({ ...extra, ...row });
  });

  app.post(base, async (c) => {
    const denied = await requireWriter(c, spec.scope);
    if (denied) return denied;
    const body = await readBody(c);
    if (body === null) return c.json({ error: 'invalid body' }, 400);
    const [keys, values] = pick(body, spec.columns);
    const invalid = invalidBody(keys, values, spec.required, spec.notNull) ?? problem(spec, body, 'create');
    if (invalid) return c.json(invalid, 400);
    const result = await insertRow(c, spec, keys, values, body);
    if ('error' in result) return c.json({ error: result.error }, result.status);
    return c.json({ id: result.id });
  });

  app.patch(`${base}/:id`, async (c) => {
    const denied = await requireWriter(c, spec.scope);
    if (denied) return denied;
    const id = c.req.param('id');
    const body = await readBody(c);
    if (body === null) return c.json({ error: 'invalid body' }, 400);
    // Existence is checked up front, before any batch is built. Batching the
    // UPDATE together with the event insert against a nonexistent id would
    // let the event's case_id foreign key throw before the UPDATE's
    // meta.changes could ever be inspected — so the 404 has to be resolved
    // here, not by reading the write's result afterwards.
    const existing = await c.env.DB.prepare(`SELECT id FROM ${spec.table} WHERE id = ?1`).bind(id).first();
    if (!existing) return c.json({ error: 'not found' }, 404);
    const [keys, values] = pick(body, spec.columns);
    // No `required` here on purpose — a PATCH is legitimately partial. But
    // `notNull` does apply: blanking a NOT NULL field on an edit form sends
    // an explicit null, which is a 400, not a 500.
    const invalid = invalidBody(keys, values, undefined, spec.notNull) ?? problem(spec, body, 'update');
    if (invalid) return c.json(invalid, 400);
    // A PATCH that writes nothing used to answer 200 — the shape that let
    // `PATCH {archived: 1}` on a spec without an `archived` column report
    // success while changing nothing. Naming the dropped keys makes the next
    // occurrence self-diagnosing instead of silent.
    if (!keys.length) {
      const ignored = Object.keys(body);
      return c.json(
        {
          error: ignored.length
            ? `no writable field(s) in body — ignored: ${ignored.join(', ')}`
            : 'no writable field(s) in body',
        },
        400,
      );
    }
    const sets = keys.map((k, i) => `${k} = ?${i + 1}`);
    // datetime('now') is a hardcoded SQL literal, not user input — safe to
    // splice in directly, and it needs no bound parameter.
    if (touchUpdatedAt) sets.push(`updated_at = datetime('now')`);
    const updateStmt = c.env.DB.prepare(`UPDATE ${spec.table} SET ${sets.join(', ')} WHERE id = ?${keys.length + 1}`).bind(
      ...values,
      id,
    );
    const ev = spec.eventStmt?.(c, id, 'updated');
    const conflict = await batchOrConflict(c.env.DB, ev ? [updateStmt, ev] : [updateStmt]);
    if (conflict) return c.json({ error: conflict.error }, conflict.status);
    return c.json({ id });
  });
}
