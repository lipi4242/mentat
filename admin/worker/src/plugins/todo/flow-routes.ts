import type { Hono } from 'hono';
import { keys, object, Problem, textField, type TodoEnv } from './types';
import { actorId, enabledPrincipal } from './kinds';
import { currentItem } from './item-store';
import { allowed, SIMPLE, transition } from './flow';
import { submitMove, verdictMove } from './flow-review';

const FROM = { submit: ['taken'], accept: ['review'], reject: ['review'] } as const;
export function registerFlow(app: Hono<TodoEnv>) {
  for (const verb of Object.keys(SIMPLE)) {
    app.post(`/items/:id/${verb}`, async c => {
      const body = object(await c.req.json()); keys(body, verb === 'issue' ? ['dev', 'note', 'expected_rev'] : ['note', 'expected_rev']);
      const item = await currentItem(c, body); if (item instanceof Response) return item;
      const probe = SIMPLE[verb](item, { dev: '', note: null });
      allowed(c, item, verb, probe.from, probe.by);
      const note = body.note == null ? null : textField(body.note, 'note', 10000);
      if (verb === 'handback' && !note) throw new Problem('handback needs a note');
      let dev: string | undefined;
      if (verb === 'issue') {
        dev = await enabledPrincipal(c.env.DB, body.dev, 'dev');
        if (!await c.env.DB.prepare('SELECT 1 FROM backlog_ac WHERE item_id = ? AND removed_at IS NULL').bind(item.id).first()) throw new Problem('issue needs at least one live AC');
      }
      return transition(c, item, SIMPLE[verb](item, { dev, note }));
    });
  }
  for (const verb of ['submit', 'accept', 'reject'] as const) {
    app.post(`/items/:id/${verb}`, async c => {
      const body = object(await c.req.json());
      keys(body, verb === 'submit' ? ['round', 'results', 'summary', 'body', 'head_sha', 'links', 'expected_rev'] : ['checks', 'note', 'expected_rev']);
      const item = await currentItem(c, body); if (item instanceof Response) return item;
      allowed(c, item, verb, [...FROM[verb]], verb === 'submit' ? 'dev' : 'pm');
      const move = verb === 'submit' ? await submitMove(c.env.DB, item, actorId(c), body)
        : await verdictMove(c.env.DB, item, actorId(c), body, verb === 'accept');
      return transition(c, item, move);
    });
  }
}
