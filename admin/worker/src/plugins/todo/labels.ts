import type { Hono } from 'hono';
import { current, event, marked, mutate } from './store';
import { newId } from './id';
import { keys, object, Problem, textField, type TodoEnv } from './types';
export function registerLabels(app: Hono<TodoEnv>) {
  app.get('/labels', async c => c.json((await c.env.DB.prepare('SELECT * FROM todo_label ORDER BY name').all()).results));
  app.post('/labels', async c => {
    const body = object(await c.req.json()); keys(body, ['name','color','idem_key']);
    const db = c.env.DB, actor = c.get('principal')!.id, key = textField(body.idem_key, 'idem_key');
    const replay = () => db.prepare('SELECT * FROM todo_label WHERE created_by=? AND idem_key=?').bind(actor, key).first();
    const existing = await replay(); if (existing) return c.json(existing);
    const name = textField(body.name, 'name'), color = body.color ?? null, id = newId();
    if (color !== null && (typeof color !== 'string' || !/^#[\da-fA-F]{6}$/.test(color))) throw new Problem('color must be #RRGGBB');
    try {
      await db.batch([db.prepare('INSERT INTO todo_label (id,name,color,created_by,idem_key) VALUES (?,?,?,?,?)').bind(id, name, color, actor, key),
        event(db, actor, 'label_created', { id, name, color }, [actor])]);
    } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) { const won = await replay(); if (won) return c.json(won); throw new Problem('label name already exists'); }
      throw e;
    }
    return c.json(await db.prepare('SELECT * FROM todo_label WHERE id=?').bind(id).first(), 201);
  });
  app.post('/tasks/:id/labels', async c => {
    const body = object(await c.req.json()); keys(body, ['label_ids','expected_rev']);
    const row = await current(c, body); if (row instanceof Response) return row;
    if (!Array.isArray(body.label_ids) || body.label_ids.length > 100 || body.label_ids.some(id => typeof id !== 'string')) throw new Problem('label_ids must be a list of up to 100 ids');
    const ids = [...new Set(body.label_ids as string[])], db = c.env.DB;
    if (ids.length && (await db.prepare(`SELECT id FROM todo_label WHERE id IN (${ids.map(() => '?').join(',')})`).bind(...ids).all()).results.length !== ids.length) throw new Problem('unknown label_ids');
    return mutate(c, row, 'labels_updated', {}, { diff: { label_ids: ids }, related: op => [
      db.prepare(`DELETE FROM todo_task_label WHERE task_id=? AND ${marked}`).bind(row.id, op),
      ...ids.map(id => db.prepare(`INSERT INTO todo_task_label SELECT ?,? WHERE ${marked}`).bind(row.id, id, op)),
    ] });
  });
}
