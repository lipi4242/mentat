import type { Hono } from 'hono';
import { current, mutate } from './store';
import { keys, object, Problem, type TodoEnv } from './types';
import { position } from './validate';
import { checkParent, projectOf } from './kinds';
// Evaluated inside the event INSERT as well as before it; UNION terminates even
// if an imported database already contains a cycle.
export const treeGuard = `NOT EXISTS (WITH RECURSIVE descendants(id) AS (
  SELECT ? UNION SELECT t.id FROM todo_task t JOIN descendants d ON t.parent_id = d.id
) SELECT 1 FROM descendants WHERE id = ?)`;
export async function parentExists(db: D1Database, parent: unknown) {
  if (parent !== null && (typeof parent !== 'string' || !await db.prepare('SELECT 1 FROM todo_task WHERE id = ?').bind(parent).first())) throw new Problem('parent_id does not exist');
}
export async function appendPosition(db: D1Database, parent: string | null) {
  const last = await db.prepare('SELECT position FROM todo_task WHERE parent_id IS ? ORDER BY position DESC LIMIT 1').bind(parent).first<{ position: string }>();
  return after(last?.position ?? null);
}
/** The next position after `last`; ties from concurrent creators are ordered by id. */
export function after(last: string | null) {
  if (last === null) return 'U';
  const chars = [...last];
  for (let i = chars.length - 1; i >= 0; i--) {
    if (chars[i] < '~') return chars.slice(0, i).join('') + String.fromCharCode(chars[i].charCodeAt(0) + 1);
  }
  return position(`${last}U`);
}
export function registerTree(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/move', async c => {
    const body = object(await c.req.json()); keys(body, ['parent_id','position','expected_rev']);
    const row = await current(c, body); if (row instanceof Response) return row;
    await parentExists(c.env.DB, body.parent_id);
    const parent = body.parent_id as string | null;
    await checkParent(c.env.DB, row.kind, parent, row.kind === 'item' ? await projectOf(c.env.DB, row.id) : null);
    const args = [row.id, parent];
    if (!(await c.env.DB.prepare(`SELECT ${treeGuard} AS ok`).bind(...args).first<{ ok: number }>())?.ok) throw new Problem('parent_id would create a tree cycle');
    return mutate(c, row, 'moved', { parent_id: parent, position: body.position === undefined ? await appendPosition(c.env.DB, parent) : position(body.position) }, { guard: treeGuard, guardArgs: args });
  });
}
