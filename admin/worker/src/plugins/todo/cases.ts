import type { Context, Hono } from 'hono';
import { current, getTask, marked, mutate, now } from './store';
import { keys, object, Problem, textField, type Task, type TodoEnv } from './types';
import { actorId, handleId, isHuman } from './kinds';
import { caseDetail } from './case-fields';
const view = (db: D1Database, id: string) => getTask(db, id).then(t => t && caseDetail(db, t));
async function openCase(c: Context<TodoEnv>, allowed: string[]) {
  const body = object(await c.req.json()); keys(body, allowed);
  const row = await current(c, body); if (row instanceof Response) return { row, body };
  if (row.kind !== 'case') throw new Problem('this endpoint is for cases');
  return { row, body };
}
export function registerCases(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/review', async c => {
    const { row, body } = await openCase(c, ['note','expected_rev']); if (row instanceof Response) return row;
    const actor = actorId(c);
    if (actor !== row.owner_id && actor !== row.assignee_id) throw new Problem('only the owner or assignee reviews a case', 403);
    const note = body.note === undefined ? null : textField(body.note, 'note', 10000), at = now();
    return mutate(c, row, 'case_reviewed', {}, { diff: { note, last_reviewed_at: at }, view,
      related: op => [c.env.DB.prepare(`UPDATE todo_case SET last_reviewed_at = ?, last_reviewed_by = ? WHERE task_id = ? AND ${marked}`).bind(at, actor, row.id, op)] });
  });
  app.post('/tasks/:id/confirm', async c => {
    const body = object(await c.req.json()); keys(body, ['expected_rev']);
    const db = c.env.DB, row = await getTask(db, c.req.param('id'));
    if (!row) throw new Problem('task not found', 404);
    if (row.kind !== 'case') throw new Problem('this endpoint is for cases');
    if (!isHuman(c)) throw new Problem('only a human confirms a case', 403);
    const shown = await view(db, row.id) as unknown as { case: { confirmed_at: string | null } };
    if (shown.case.confirmed_at) return c.json(shown);
    if (body.expected_rev !== row.rev) return c.json({ error: 'revision conflict', current: shown }, 409);
    const actor = actorId(c), at = now();
    return mutate(c, row, 'case_confirmed', {}, { diff: { confirmed_at: at }, view,
      guard: 'EXISTS (SELECT 1 FROM todo_case WHERE task_id = ? AND confirmed_at IS NULL)', guardArgs: [row.id],
      related: op => [db.prepare(`UPDATE todo_case SET confirmed_at = ?, confirmed_by = ? WHERE task_id = ? AND ${marked}`).bind(at, actor, row.id, op)] });
  });
  app.get('/cases/review-due', async c => {
    const handle = c.req.query('for'), db = c.env.DB, args: string[] = [];
    const ball = handle === undefined ? '' : (args.push(await handleId(db, 'for', handle)), 'AND coalesce(t.assignee_id, t.owner_id) = ?');
    const since = 'julianday(coalesce(k.last_reviewed_at, t.created_at))';
    const { results } = await db.prepare(`SELECT t.*, k.goal, k.frame, k.next_action, k.waiting_on, k.due_reason, k.brain_ref,
        k.review_every, k.last_reviewed_at, k.last_reviewed_by, k.confirmed_at, k.confirmed_by,
        julianday('now') - ${since} - k.review_every AS overdue_days
      FROM todo_task t JOIN todo_case k ON k.task_id = t.id
      WHERE t.kind = 'case' AND t.status = 'open' AND t.archived = 0 AND k.confirmed_at IS NOT NULL
        AND k.review_every IS NOT NULL AND ${since} + k.review_every <= julianday('now') ${ball}
      ORDER BY overdue_days DESC, t.id`).bind(...args).all<Task>();
    return c.json(results);
  });
}
