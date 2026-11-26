import type { Hono } from 'hono';
import { Problem, type TodoEnv } from './types';
import { isHuman } from './kinds';
import { requireSelf } from './visible';
export function registerEvents(app: Hono<TodoEnv>) {
  app.get('/changes', async c => {
    const since = c.req.query('since') ?? '0', limit = c.req.query('limit') ?? '100', handle = c.req.query('for');
    if (!/^\d+$/.test(since) || !Number.isSafeInteger(Number(since)) || !/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > 500) throw new Problem('since must be a nonnegative integer; limit 1–500');
    const p = handle === undefined ? null : await c.env.DB.prepare('SELECT id FROM todo_principal WHERE handle=?').bind(handle).first<{ id: string }>();
    if (handle !== undefined && !p) throw new Problem('for must be a known handle');
    requireSelf(c, p?.id ?? null);
    const who = p ?? (isHuman(c) ? null : { id: c.get('principal')!.id }); // an agent's feed is its own
    const events = await c.env.DB.prepare(`SELECT * FROM todo_event WHERE seq > ? ${who ? 'AND EXISTS (SELECT 1 FROM json_each(recipients_json) WHERE value=?)' : ''} ORDER BY seq LIMIT ?`)
      .bind(Number(since), ...(who ? [who.id] : []), Number(limit)).all();
    return c.json(events.results);
  });
}
