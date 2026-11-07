import type { Hono } from 'hono';
import { current, marked, mutate, now } from './store';
import { keys, object, Problem, type Fields, type TodoEnv } from './types';
import { nextDate, todayIn } from './recurrence';
import { refuseItem } from './kinds';
import { caseChildren } from './case-complete';
// A dropped/archived branch stays released, including its descendants.
const checklist = `WITH RECURSIVE checklist(id) AS (
  SELECT id FROM todo_task WHERE parent_id = ? AND archived = 0 AND status <> 'dropped'
  UNION SELECT t.id FROM todo_task t JOIN checklist c ON t.parent_id = c.id
  WHERE t.archived = 0 AND t.status <> 'dropped')`;
export function registerComplete(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/complete', async c => {
    const body = object(await c.req.json()); keys(body, ['expected_rev','children']);
    const row = await current(c, body); if (row instanceof Response) return row;
    refuseItem(row, 'complete');
    if (row.status !== 'open' || row.archived) throw new Problem('complete requires an open, unarchived task');
    const actor = c.get('principal')!.id, db = c.env.DB, at = now();
    const set: Fields = { status: 'done', done_at: at, done_by: actor, assignee_id: null, assignee_note: null };
    if (row.kind === 'case') {
      const plan = await caseChildren(c, row, body.children);
      if (plan instanceof Response) return plan;
      return mutate(c, row, 'completed', set, { diff: { ...set, children: body.children ?? null }, ...plan });
    }
    if (body.children !== undefined) throw new Problem('children applies only to a case');
    if (row.repeat_rule) {
      const date = nextDate(row.repeat_rule, row.due_date!, todayIn(row.tz), row.repeat_from);
      Object.assign(set, { status: 'open', due_date: date, done_at: null, done_by: null });
    }
    return mutate(c, row, row.repeat_rule ? 'occurrence_done' : 'completed', set, {
      diff: { ...set, completed_due_date: row.due_date, completed_at: at },
      related: row.repeat_rule ? op => [
        db.prepare(`${checklist} INSERT INTO todo_event (op_id,task_id,at,actor_id,kind,diff_json,recipients_json)
          SELECT ? || ':' || t.id, t.id, ?, ?, 'checklist_reset', json_object('status','open','rev',t.rev+1),
          (SELECT json_group_array(DISTINCT value) FROM (
            SELECT t.owner_id AS value UNION SELECT t.assignee_id WHERE t.assignee_id IS NOT NULL
            UNION SELECT principal_id FROM todo_mention WHERE source_kind='task' AND source_id=t.id))
          FROM todo_task t JOIN checklist ch ON ch.id=t.id WHERE t.status='done' AND ${marked}`)
          .bind(row.id, op, at, actor, op),
        db.prepare(`UPDATE todo_task SET status='open',done_at=NULL,done_by=NULL,rev=rev+1,updated_at=?,updated_by=?
          WHERE id IN (SELECT task_id FROM todo_event WHERE kind='checklist_reset' AND op_id = ? || ':' || todo_task.id)`)
          .bind(at, actor, op),
      ] : undefined,
    });
  });
}
