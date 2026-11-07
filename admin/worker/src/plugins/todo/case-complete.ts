// Completing a case: open descendants are closed or kept only on request.
// The checks run again inside the batch (guard), so a child created after the
// read cannot slip under a completed case.
import type { Context } from 'hono';
import { marked, now } from './store';
import { Problem, type Task, type TodoEnv } from './types';

const TREE = `WITH RECURSIVE sub(id) AS (SELECT id FROM todo_task WHERE parent_id = ?
  UNION SELECT t.id FROM todo_task t JOIN sub s ON t.parent_id = s.id)`;
const open = (kinds: string) => `SELECT t.id FROM todo_task t JOIN sub s ON s.id = t.id
  WHERE t.status = 'open' AND t.archived = 0 AND t.kind IN (${kinds})`;
const noneOpen = (kinds: string) => `NOT EXISTS (${TREE} ${open(kinds)})`;

export async function caseChildren(c: Context<TodoEnv>, row: Task, children: unknown) {
  if (children !== undefined && children !== 'close' && children !== 'keep') throw new Problem('children must be close or keep');
  const db = c.env.DB;
  const list = async (kinds: string) => (await db.prepare(`${TREE} ${open(kinds)}`).bind(row.id).all<{ id: string }>()).results.map(r => r.id);
  // An item ends only by accept or drop, so it always blocks.
  const items = await list("'item'");
  if (items.length) return c.json({ error: 'an open backlog item is under this case', open_children: items, current: row }, 409);
  if (children === undefined) {
    const todos = await list("'todo','case'");
    if (todos.length) return c.json({ error: 'case has open children; send children: close or keep', open_children: todos, current: row }, 409);
    return { guard: noneOpen("'todo','case','item'"), guardArgs: [row.id] };
  }
  const plan = { guard: noneOpen("'item'"), guardArgs: [row.id] };
  if (children === 'keep') return plan;
  const actor = c.get('principal')!.id, at = now();
  return { ...plan, related: (op: string) => [
    db.prepare(`${TREE} INSERT INTO todo_event (op_id,task_id,at,actor_id,kind,diff_json,recipients_json)
      SELECT ? || ':' || t.id, t.id, ?, ?, 'completed', json_object('status','done','closed_with_case',?),
      (SELECT json_group_array(DISTINCT value) FROM (
        SELECT t.owner_id AS value UNION SELECT t.assignee_id WHERE t.assignee_id IS NOT NULL
        UNION SELECT principal_id FROM todo_mention WHERE source_kind='task' AND source_id=t.id))
      FROM todo_task t JOIN sub s ON s.id = t.id
      WHERE t.status = 'open' AND t.archived = 0 AND t.kind = 'todo' AND ${marked}`)
      .bind(row.id, op, at, actor, row.id, op),
    db.prepare(`UPDATE todo_task SET status='done', done_at=?, done_by=?, assignee_id=NULL, assignee_note=NULL,
      rev=rev+1, updated_at=?, updated_by=?
      WHERE id IN (SELECT task_id FROM todo_event WHERE kind='completed' AND op_id = ? || ':' || todo_task.id)`)
      .bind(at, actor, at, actor, op),
  ] };
}
