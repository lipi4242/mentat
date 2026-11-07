import type { Context } from 'hono';
import type { TodoEnv, Task, Fields } from './types';
import { Problem } from './types';
import { newId } from './id';
import { withProgress } from './progress';
export const now = () => new Date().toISOString();
export const getTask = (db: D1Database, id: string) => db.prepare('SELECT * FROM todo_task WHERE id = ?').bind(id).first<Task>();
export const marked = 'EXISTS (SELECT 1 FROM todo_event WHERE op_id = ?)';
export function event(db: D1Database, actor: string, kind: string, diff: unknown, recipients: string[], task: string | null = null) {
  return db.prepare(`INSERT INTO todo_event (op_id, task_id, at, actor_id, kind, diff_json, recipients_json) VALUES (?,?,?,?,?,?,?)`)
    .bind(newId(), task, now(), actor, kind, JSON.stringify(diff), JSON.stringify([...new Set(recipients)]));
}
export async function current(c: Context<TodoEnv>, body: Record<string, unknown>) {
  const row = await getTask(c.env.DB, c.req.param('id')!);
  if (!row) throw new Problem('task not found', 404);
  if (body.expected_rev !== row.rev) return c.json({ error: 'revision conflict', current: row }, 409);
  return row;
}
// Event first is the transaction's authorization marker. Related writes only run
// if that exact operation won the revision AND graph guard, never merely rev+1.
export async function mutate(c: Context<TodoEnv>, row: Task, kind: string, set: Fields, options: {
  diff?: unknown; recipients?: string[]; guard?: string; guardArgs?: unknown[];
  related?: (op: string) => D1PreparedStatement[];
  view?: (db: D1Database, id: string) => Promise<unknown>;
} = {}) {
  const db = c.env.DB, op = newId(), actor = c.get('principal')!.id, at = now();
  const recipients = [row.owner_id, row.assignee_id, set.owner_id, set.assignee_id, ...(options.recipients ?? [])].filter(v => typeof v === 'string');
  const insert = db.prepare(`INSERT INTO todo_event (op_id,task_id,at,actor_id,kind,diff_json,recipients_json)
    SELECT ?,?,?,?,?,?, (SELECT json_group_array(DISTINCT value) FROM (
      SELECT value FROM json_each(?) WHERE value IS NOT NULL UNION
      SELECT principal_id FROM todo_mention WHERE source_kind = 'task' AND source_id = ?))
    WHERE EXISTS (SELECT 1 FROM todo_task WHERE id = ? AND rev = ?) AND (${options.guard ?? '1'})`)
    .bind(op, row.id, at, actor, kind, JSON.stringify(options.diff ?? set), JSON.stringify(recipients), row.id, row.id, row.rev, ...(options.guardArgs ?? []));
  const fields = { ...set, updated_at: at, updated_by: actor };
  const update = db.prepare(`UPDATE todo_task SET ${Object.keys(fields).map(k => `${k} = ?`).join(',')}, rev = rev + 1 WHERE id = ? AND ${marked}`)
    .bind(...Object.values(fields), row.id, op);
  const results = await db.batch([insert, ...(options.related?.(op) ?? []), update]);
  const view = options.view ?? getTask;
  if (!results[0].meta.changes) return c.json({ error: 'revision or graph conflict', current: await view(db, row.id) }, 409);
  return c.json(await view(db, row.id));
}
export async function detail(db: D1Database, id: string) {
  const row = await getTask(db, id);
  if (!row) throw new Problem('task not found', 404);
  const [children, labels, comments, deps] = await Promise.all([
    db.prepare('SELECT * FROM todo_task WHERE parent_id = ? ORDER BY position,id').bind(id).all<Task>(),
    db.prepare('SELECT l.* FROM todo_label l JOIN todo_task_label t ON t.label_id = l.id WHERE t.task_id = ?').bind(id).all(),
    db.prepare(`SELECT c.*, p.display_name, p.handle, p.kind, p.avatar FROM todo_comment c JOIN todo_principal p ON p.id = c.author_id WHERE task_id = ? ORDER BY created_at,c.id`).bind(id).all(),
    db.prepare('SELECT depends_on_id FROM todo_dep WHERE task_id = ?').bind(id).all(),
  ]);
  const [task, ...childRows] = await withProgress(db, [row, ...children.results]);
  return { ...task, children: childRows, labels: labels.results, comments: comments.results, deps: deps.results };
}
