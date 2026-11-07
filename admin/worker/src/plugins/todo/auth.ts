import type { MiddlewareHandler } from 'hono';
import { hasScope, resolveAgentToken } from '../../lib/guards';
import { createAuth } from '../../lib/better-auth';
import { adminEmails } from '../../types';
import type { Principal, TodoEnv } from './types';
export const authenticate: MiddlewareHandler<TodoEnv> = async (c, next) => {
  const supplied = c.req.header('X-Mentat-Token');
  c.set('email', null);
  let principal: Principal | null = null;
  if (supplied !== undefined) {
    const token = await resolveAgentToken(c.env.DB, supplied);
    if (!token || !hasScope(token.scopes, 'todo:write')) return c.json({ error: 'forbidden' }, 403);
    principal = await c.env.DB.prepare(`SELECT * FROM todo_principal WHERE agent_token_id = ? AND disabled_at IS NULL`).bind(token.id).first<Principal>();
  } else {
    if (!c.env.BETTER_AUTH_SECRET) return c.json({ error: 'unauthorized' }, 401);
    const session = await createAuth(c.env).api.getSession({ headers: c.req.raw.headers }).catch(() => null);
    const email = session?.user.email.toLowerCase();
    if (!email || !adminEmails(c.env).includes(email)) return c.json({ error: 'unauthorized' }, 401);
    c.set('email', email);
    principal = await c.env.DB.prepare(`SELECT * FROM todo_principal WHERE auth_email = ? AND disabled_at IS NULL`).bind(email).first<Principal>();
  }
  c.set('principal', principal);
  if (!principal && !(c.get('email') && c.req.method === 'POST' && c.req.path.endsWith('/principals'))) {
    return c.json({ error: 'principal is unknown or disabled' }, 403);
  }
  await next();
};
