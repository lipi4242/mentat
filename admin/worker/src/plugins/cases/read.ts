// Reads: the list, the due window, the change feed, and one case in full.
// A `cases:read` or a `cases:write` token may read.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireWriter } from '../../lib/guards';
import { isIsoDate } from './recurrence';
import { detail, openDates, toJson, type CaseRow } from './store';
import { STATUSES } from './validate';

export const READ = ['cases:read', 'cases:write'];

// Undated cases last, then by date and title. `SELECT *` so the instance's
// own fields come along whatever they are; `context` is dropped after the read
// (the heaviest column, and only the detail view shows it).
const LIST_SQL = `SELECT * FROM cases_case`;
const ORDER = `ORDER BY due_at IS NULL, due_at, title`;
const listItem = ({ context: _context, ...row }: CaseRow) => toJson(row as CaseRow);

export function registerReads(app: Hono<AppEnv>) {
  app.get('/api/cases', async (c) => {
    const denied = await requireWriter(c, READ);
    if (denied) return denied;
    const want = (c.req.query('status') ?? '').split(',').filter(Boolean);
    if (want.some((s) => !STATUSES.includes(s as never))) return c.json({ error: `status must be among ${STATUSES.join(', ')}` }, 422);
    const where = want.length ? `WHERE status IN (${want.map((_, i) => `?${i + 1}`).join(', ')})` : '';
    const { results } = await c.env.DB.prepare(`${LIST_SQL} ${where} ${ORDER}`).bind(...want).all<CaseRow>();
    return c.json(results.map(listItem), 200, { 'X-Total-Count': String(results.length) });
  });

  // Every open occurrence due on or before `until`, one item per date. Only
  // the first of each case is `closable` — the rest wait behind it.
  app.get('/api/cases/due', async (c) => {
    const denied = await requireWriter(c, READ);
    if (denied) return denied;
    const until = c.req.query('until');
    if (!isIsoDate(until)) return c.json({ error: 'until must be a YYYY-MM-DD date' }, 422);
    const { results } = await c.env.DB.prepare(
      `SELECT * FROM cases_case WHERE status IN ('open', 'waiting') AND due_at IS NOT NULL AND due_at <= ?1 ${ORDER}`,
    )
      .bind(until)
      .all<CaseRow>();
    const items = results.flatMap((row) =>
      openDates(row, until).map((due_at, i) => ({
        case_id: row.id,
        title: row.title,
        status: row.status,
        description: row.description,
        next_action: row.next_action,
        recurrence: row.recurrence,
        brain_ref: row.brain_ref,
        due_at,
        closable: i === 0,
      })),
    );
    items.sort((a, b) => a.due_at.localeCompare(b.due_at) || a.title.localeCompare(b.title));
    return c.json(items);
  });

  // The change feed for `cases sync`: events after an id cursor, oldest first.
  app.get('/api/cases/events', async (c) => {
    const denied = await requireWriter(c, READ);
    if (denied) return denied;
    const after = c.req.query('after') ?? '0';
    const limit = c.req.query('limit') ?? '100';
    if (!/^\d+$/.test(after) || !/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > 500) {
      return c.json({ error: 'after must be an event id (0 for the start), limit 1–500' }, 422);
    }
    const { results } = await c.env.DB.prepare(
      `SELECT id, case_id, at, actor, actor_token_id, kind, body FROM cases_event WHERE id > ?1 ORDER BY id LIMIT ?2`,
    )
      .bind(Number(after), Number(limit))
      .all();
    return c.json(results);
  });

  app.get('/api/cases/:id', async (c) => {
    const denied = await requireWriter(c, READ);
    if (denied) return denied;
    const one = await detail(c.env.DB, c.req.param('id'));
    return one ? c.json(one) : c.json({ error: 'not found' }, 404);
  });
}
