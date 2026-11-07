import type { Hono } from 'hono';
import { current, marked, mutate, now } from './store';
import { keys, object, textField, type TodoEnv } from './types';
import { mentions, mentionStatements } from './mentions';
import { newId } from './id';
export function registerComments(app: Hono<TodoEnv>) {
  app.post('/tasks/:id/comments', async c => {
    const body = object(await c.req.json()); keys(body, ['body','expected_rev']);
    const row = await current(c, body); if (row instanceof Response) return row;
    const text = textField(body.body, 'body', 100000), id = newId(), db = c.env.DB;
    const ids = await mentions(db, text);
    return mutate(c, row, 'commented', {}, { diff: { comment_id: id, body: text }, recipients: ids,
      related: op => [db.prepare(`INSERT INTO todo_comment (id,task_id,author_id,body,created_at) SELECT ?,?,?,?,? WHERE ${marked}`)
        .bind(id, row.id, c.get('principal')!.id, text, now(), op), ...mentionStatements(db, 'comment', id, ids, op)] });
  });
}
