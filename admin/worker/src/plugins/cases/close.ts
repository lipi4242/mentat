// POST /api/cases/:id/occurrences — close the earliest open occurrence.
//
// Only that one can be closed, so an unpaid October never disappears behind a
// paid November. Closing a date that is already closed answers 200 with
// `already_closed` and writes nothing: a retried close is harmless and can
// never close a second occurrence.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireWriter } from '../../lib/guards';
import { checkClose } from './validate';
import { firstOpenAfter, onSeries, parseRecurrence, slotOf } from './recurrence';
import { detail, eventStmt, getCase } from './store';

export function registerClose(app: Hono<AppEnv>) {
  app.post('/api/cases/:id/occurrences', async (c) => {
    const denied = await requireWriter(c, 'cases:write');
    if (denied) return denied;
    const id = c.req.param('id');
    const body = await c.req.json().catch(() => undefined);
    if (body === undefined) return c.json({ error: 'body must be JSON' }, 400);
    const occ = checkClose(body);
    if ('error' in occ) return c.json(occ, 422);

    const DB = c.env.DB;
    const row = await getCase(DB, id);
    if (!row) return c.json({ error: 'not found' }, 404);
    const r = parseRecurrence(row.recurrence);
    if (!r || !row.anchor_at) {
      return c.json({ error: 'not a recurring case — close it with PUT status done or dropped' }, 422);
    }
    // An occurrence is named by its series date, or — for the open one — by
    // its moved date (October due on the 20th of a monthly:10 series): both
    // close the same series date, so a retry with either answers already_closed.
    const slot = slotOf(row.anchor_at, r, occ.due_at);
    const closed = slot && (await DB.prepare(`SELECT 1 FROM cases_occurrence WHERE case_id = ?1 AND due_at = ?2`).bind(id, slot).first());
    if (closed) return c.json({ ...(await detail(DB, id)), already_closed: true });
    if (!['open', 'waiting'].includes(row.status)) {
      return c.json({ error: `the case is ${row.status} — reopen it before closing an occurrence` }, 422);
    }
    if (!onSeries(row.anchor_at, r, occ.due_at) && occ.due_at !== row.due_at) {
      return c.json({ error: `${occ.due_at} is not a date of the series ${row.recurrence} from ${row.anchor_at}, nor the open one (${row.due_at})` }, 422);
    }
    const open = row.due_at ? slotOf(row.anchor_at, r, row.due_at) : null;
    if (!slot || slot !== open) {
      return c.json({ error: 'only the earliest open occurrence can be closed', earliest_open: row.due_at }, 409);
    }
    occ.due_at = slot;

    const next = firstOpenAfter(row.anchor_at, r, occ.due_at);
    // All three are guarded by the version just read, and the UPDATE runs
    // last: either the whole close lands, or — if anything changed in
    // between — none of it does.
    const results = await DB.batch([
      DB.prepare(
        `INSERT INTO cases_occurrence (case_id, due_at, status, done_at, note)
           SELECT ?1, ?2, ?3, ?4, ?5 WHERE (SELECT version FROM cases_case WHERE id = ?1) = ?6`,
      ).bind(id, occ.due_at, occ.status, occ.done_at, occ.note, row.version),
      eventStmt(c, id, row.version, 'occurrence.closed', { due_at: occ.due_at, status: occ.status, next_due_at: next }),
      DB.prepare(
        `UPDATE cases_case SET due_at = ?1, version = version + 1, updated_at = datetime('now') WHERE id = ?2 AND version = ?3`,
      ).bind(next, id, row.version),
    ]);
    if (!results[2].meta.changes) {
      return c.json({ error: 'the case changed concurrently — re-read it and retry' }, 409);
    }
    return c.json(await detail(DB, id));
  });
}
