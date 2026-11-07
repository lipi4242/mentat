import type { Hono } from 'hono';
import { current, marked, mutate } from './store';
import { keys, object, Problem, textField, type TodoEnv } from './types';
const acyclic = `NOT EXISTS (WITH RECURSIVE links(id) AS (
  SELECT ? UNION SELECT d.depends_on_id FROM todo_dep d JOIN links l ON d.task_id=l.id
) SELECT 1 FROM links WHERE id = ?)`;
export function registerDeps(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/deps', async c => {
    const body = object(await c.req.json()); keys(body, ['depends_on_id','remove','expected_rev']);
    const row = await current(c, body); if (row instanceof Response) return row;
    const dep = textField(body.depends_on_id, 'depends_on_id'), db = c.env.DB;
    if (body.remove !== undefined && typeof body.remove !== 'boolean') throw new Problem('remove must be boolean');
    if (!await db.prepare('SELECT 1 FROM todo_task WHERE id = ?').bind(dep).first()) throw new Problem('depends_on_id does not exist');
    const args = [dep, row.id];
    if (!body.remove && !(await db.prepare(`SELECT ${acyclic} AS ok`).bind(...args).first<{ ok: number }>())?.ok) throw new Problem('dependency cycle');
    return mutate(c, row, 'dependencies_updated', {}, { diff: { depends_on_id: dep, remove: !!body.remove },
      guard: body.remove ? '1' : acyclic, guardArgs: body.remove ? [] : args,
      related: op => [body.remove
        ? db.prepare(`DELETE FROM todo_dep WHERE task_id=? AND depends_on_id=? AND ${marked}`).bind(row.id, dep, op)
        : db.prepare(`INSERT OR IGNORE INTO todo_dep SELECT ?,? WHERE ${marked}`).bind(row.id, dep, op)] });
  });
}
