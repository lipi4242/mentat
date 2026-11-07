import type { Hono } from 'hono';
import { detail } from './store';
import { isIsoDate } from './recurrence';
import { withProgress } from './progress';
import { Problem, type Task, type TodoEnv } from './types';
import { handleId, KINDS } from './kinds';
import { caseDetail } from './case-fields';
export function registerRead(app: Hono<TodoEnv>) {
  app.get('/tasks', async c => {
    const q = c.req.query(), where: string[] = [], args: string[] = [];
    if (q.root !== undefined && q.root !== '1') throw new Problem('root must be 1');
    if (q.root && q.parent) throw new Problem('choose root or parent');
    if (q.root || q.parent === '') where.push('parent_id IS NULL');
    else if (q.parent) { where.push('parent_id=?'); args.push(q.parent); }
    const db = c.env.DB;
    if (q.ball !== undefined) { where.push('coalesce(assignee_id,owner_id)=?'); args.push(await handleId(db, 'ball', q.ball)); }
    if (q.owner !== undefined) { where.push('owner_id=?'); args.push(await handleId(db, 'owner', q.owner)); }
    if (q.assignee === '') where.push('assignee_id IS NULL');
    else if (q.assignee !== undefined) { where.push('assignee_id=?'); args.push(await handleId(db, 'assignee', q.assignee)); }
    const kinds = q.kind === 'all' ? [...KINDS] : (q.kind ?? 'todo,case').split(',');
    if (kinds.some(k => !(KINDS as readonly string[]).includes(k))) throw new Problem('kind must be todo, case, item, a comma list of them, or all');
    where.push(`kind IN (${kinds.map(() => '?').join(',')})`); args.push(...kinds);
    if (q.label) { where.push('id IN (SELECT task_id FROM todo_task_label WHERE label_id=?)'); args.push(q.label); }
    if (q.status) {
      if (!['open','done','dropped'].includes(q.status)) throw new Problem('status must be open, done or dropped');
      where.push('status=?'); args.push(q.status);
    }
    if (q.due_before) {
      if (!isIsoDate(q.due_before)) throw new Problem('due_before must be YYYY-MM-DD');
      where.push('due_date <= ?'); args.push(q.due_before);
    }
    const { results } = await c.env.DB.prepare(`SELECT * FROM todo_task ${where.length ? `WHERE ${where.join(' AND ')}` : ''} ORDER BY position,id`).bind(...args).all<Task>();
    return c.json(await withProgress(c.env.DB, results), 200, { 'X-Total-Count': String(results.length) });
  });
  app.get('/tasks/:id', async c => c.json(await caseDetail(c.env.DB, await detail(c.env.DB, c.req.param('id')))));
}
