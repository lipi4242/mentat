// Reading backlog items: the anchor todo_task joined to its backlog_item row,
// key resolution (ULID or PREFIX-N), and the full detail view.
import type { Context } from 'hono';
import { detail } from './store';
import { Problem, type Task, type TodoEnv } from './types';
import { isHuman } from './kinds';

export const STAGES = ['draft', 'issued', 'taken', 'review', 'done', 'hold', 'dropped'] as const;
export type Stage = typeof STAGES[number];
export type Item = Task & {
  project_id: string; number: number; stage: Stage; priority: number; estimate: number | null;
  dev_id: string | null; hold_from: Stage | null; request_quote: string | null; request_ref: string | null;
  issued_at: string | null; taken_at: string | null; ext_ref: string | null; key: string;
};
export const ITEM_SELECT = `SELECT t.*, b.project_id, b.number, b.stage, b.priority, b.estimate, b.dev_id, b.hold_from,
  b.request_quote, b.request_ref, b.issued_at, b.taken_at, b.ext_ref, p.prefix || '-' || b.number AS key
  FROM todo_task t JOIN backlog_item b ON b.task_id = t.id JOIN backlog_project p ON p.id = b.project_id`;

export const getItem = (db: D1Database, id: string) => db.prepare(`${ITEM_SELECT} WHERE t.id = ?`).bind(id).first<Item>();

/** `GET /items/:ref`: a ULID, or PREFIX-N in any case. */
export async function resolveRef(db: D1Database, ref: string) {
  const key = /^([A-Za-z][A-Za-z0-9]{0,7})-(\d+)$/.exec(ref);
  if (!key) return ref;
  const row = await db.prepare(`SELECT b.task_id FROM backlog_item b JOIN backlog_project p ON p.id = b.project_id WHERE p.prefix = ? AND b.number = ?`)
    .bind(key[1].toUpperCase(), Number(key[2])).first<{ task_id: string }>();
  return row?.task_id ?? ref;
}

/** The item an endpoint acts on, with the same revision rule as `current()`. */
export async function currentItem(c: Context<TodoEnv>, body: Record<string, unknown>, id = c.req.param('id')!) {
  const item = await getItem(c.env.DB, id);
  if (!item) throw new Problem('item not found', 404);
  if (body.expected_rev !== item.rev) return c.json({ error: 'revision conflict', current: item }, 409);
  return item;
}

export function requirePm(c: Context<TodoEnv>, item: Item) {
  if (c.get('principal')!.id !== item.owner_id && !isHuman(c)) throw new Problem("only the item's PM can do this", 403);
}
export function requireDev(c: Context<TodoEnv>, item: Item) {
  if (c.get('principal')!.id !== item.dev_id) throw new Problem("only the item's developer can do this", 403);
}

export async function itemDetail(db: D1Database, id: string) {
  const item = await getItem(db, id);
  if (!item) throw new Problem('item not found', 404);
  const [base, acs, links, reports, results, events] = await Promise.all([
    detail(db, id),
    db.prepare('SELECT * FROM backlog_ac WHERE item_id = ? AND removed_at IS NULL ORDER BY position, id').bind(id).all(),
    db.prepare('SELECT * FROM backlog_link WHERE item_id = ? AND removed_at IS NULL ORDER BY created_at, id').bind(id).all(),
    db.prepare('SELECT * FROM backlog_report WHERE item_id = ? ORDER BY round').bind(id).all<{ id: string }>(),
    db.prepare(`SELECT r.* FROM backlog_ac_result r JOIN backlog_report p ON p.id = r.report_id WHERE p.item_id = ?
      ORDER BY (SELECT position FROM backlog_ac WHERE id = r.ac_id), r.ac_id`).bind(id).all<{ report_id: string }>(),
    db.prepare('SELECT * FROM todo_event WHERE task_id = ? ORDER BY seq').bind(id).all(),
  ]);
  const withResults = reports.results.map(r => ({ ...r, results: results.results.filter(x => x.report_id === r.id) }));
  return { ...base, ...item, acs: acs.results, links: links.results, reports: withResults, events: events.results };
}
