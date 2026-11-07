import type { Hono } from 'hono';
import { current, mutate } from './store';
import { keys, object, Problem, textField, type TodoEnv } from './types';
import { refuseItem } from './kinds';
export function registerHandback(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/handback', async c => {
    const body = object(await c.req.json()); keys(body, ['expected_rev','note']);
    const row = await current(c, body); if (row instanceof Response) return row;
    refuseItem(row, 'handback');
    if (row.assignee_id !== c.get('principal')!.id) throw new Problem('only the assignee can hand back', 403);
    if (row.status !== 'open' || row.archived) throw new Problem('handback requires an open, unarchived task');
    const note = body.note === undefined ? null : textField(body.note, 'note', 10000);
    return mutate(c, row, 'handback', { assignee_id: null, assignee_note: null }, { diff: { note, assignee_id: null, assignee_note: null } });
  });
}
