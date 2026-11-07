// PUT /api/cases/:id — create or update, keyed by the writer's own ULID.
//
// Idempotent by content: a PUT that changes nothing answers 200 `unchanged`
// whatever version it carries, so a retry after a lost response is harmless.
// A PUT that changes something must name the version it read (body `version`
// or `If-Match`); a stale or missing one is 409 with the current version.
import type { Context, Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireWriter } from '../../lib/guards';
import { checkPut } from './validate';
import { colsFor, resolve, type Next } from './resolve';
import { detail, eventStmt, getCase, getOccurrences, sha256 } from './store';
import type { FieldDef } from '../../core/fields';
import { missingColumns } from '../../core/models';

const isUnique = (e: unknown) => e instanceof Error && /UNIQUE constraint failed|PRIMARY KEY/i.test(e.message);

function versionOf(c: Context<AppEnv>, bodyVersion: number | undefined): number | undefined | 'bad' {
  const h = c.req.header('If-Match');
  if (h === undefined) return bodyVersion;
  const v = /^"?(\d+)"?$/.exec(h.trim());
  if (!v || (bodyVersion !== undefined && Number(v[1]) !== bodyVersion)) return 'bad';
  return Number(v[1]);
}

async function create(c: Context<AppEnv>, id: string, next: Next, occ: { due_at: string; status: string; done_at: string | null; note: string | null }[], fields: string[], cols: string[]) {
  const DB = c.env.DB;
  const stmts = [
    DB.prepare(`INSERT INTO cases_case (id, ${cols.join(', ')}) VALUES (${['id', ...cols].map((_, i) => `?${i + 1}`).join(', ')})`).bind(
      id,
      ...cols.map((k) => next[k] ?? null),
    ),
    ...occ.map((o) =>
      DB.prepare(`INSERT INTO cases_occurrence (case_id, due_at, status, done_at, note) VALUES (?1, ?2, ?3, ?4, ?5)`).bind(
        id, o.due_at, o.status, o.done_at, o.note,
      ),
    ),
    eventStmt(c, id, 1, 'case.created', { fields }),
  ];
  try {
    await DB.batch(stmts);
  } catch (e) {
    // Two creators raced on the same id: the loser re-reads and decides.
    if (isUnique(e)) return c.json({ error: 'created concurrently — re-read the case' }, 409);
    throw e;
  }
  return c.json(await detail(DB, id), 201);
}

export function registerPut(app: Hono<AppEnv>, own: readonly FieldDef[]) {
  const cols = colsFor(own);
  app.put('/api/cases/:id', async (c) => {
    const denied = await requireWriter(c, 'cases:write');
    if (denied) return denied;
    const id = c.req.param('id');
    const body = await c.req.json().catch(() => undefined);
    if (body === undefined) return c.json({ error: 'body must be JSON' }, 400);
    const input = checkPut(body, id, own);
    if ('error' in input) return c.json(input, 422);
    // A field declared in config/models.json whose migration has not run yet:
    // say which, rather than a 500 from the INSERT.
    const pending = await missingColumns(c.env.DB, 'cases_case', own.map((f) => f.name));
    if (pending.length) {
      return c.json({ error: `not migrated yet: ${pending.join(', ')} — apply the migration that adds it` }, 503);
    }
    const version = versionOf(c, input.version);
    if (version === 'bad') return c.json({ error: 'If-Match must be the version number, and agree with body.version' }, 422);

    const row = await getCase(c.env.DB, id);
    const stored = row ? { row, occurrences: await getOccurrences(c.env.DB, id) } : null;
    const ctx = input.fields.context;
    const hash = ctx === undefined ? undefined : ctx === null ? null : await sha256(ctx as string);
    const res = resolve(input, stored, hash, own);
    if ('error' in res) return c.json(res, 422);
    if (!row) return create(c, id, res.next, res.occurrences, Object.keys(input.fields), cols);

    const changed = cols.filter((k) => (res.next[k] ?? null) !== (row[k] ?? null));
    if (!changed.length) return c.json({ ...(await detail(c.env.DB, id)), unchanged: true });
    if (version !== row.version) {
      return c.json({ error: 'version conflict — re-read the case and retry with its version', version: row.version }, 409);
    }
    const sets = changed.map((k, i) => `${k} = ?${i + 1}`).join(', ');
    const n = changed.length;
    const [, upd] = await c.env.DB.batch([
      eventStmt(c, id, row.version, 'case.updated', { fields: changed }),
      c.env.DB.prepare(
        `UPDATE cases_case SET ${sets}, version = version + 1, updated_at = datetime('now') WHERE id = ?${n + 1} AND version = ?${n + 2}`,
      ).bind(...changed.map((k) => res.next[k]), id, row.version),
    ]);
    if (!upd.meta.changes) {
      const now = await getCase(c.env.DB, id);
      return c.json({ error: 'version conflict — changed concurrently', version: now?.version }, 409);
    }
    return c.json(await detail(c.env.DB, id));
  });
}
