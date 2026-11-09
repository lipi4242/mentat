import type { MiddlewareHandler } from 'hono';
import { authorize } from '../../lib/guards';
import type { Principal, TodoEnv } from './types';
// Who the caller is comes from the shared guard (lib/guards.ts) — token
// lookup, scope, expiry, session and ADMIN_EMAILS live there only. This file
// adds just the todo-specific step: mapping that caller to a live principal.
export const authenticate: MiddlewareHandler<TodoEnv> = async (c, next) => {
  c.set('email', null);
  c.set('tokenScopes', null);
  const r = await authorize(c, 'todo:write');
  if ('denied' in r) return r.denied;
  let principal: Principal | null;
  if (r.caller.kind === 'agent') {
    c.set('tokenScopes', r.caller.scopes);
    principal = await c.env.DB.prepare(`SELECT * FROM todo_principal WHERE agent_token_id = ? AND disabled_at IS NULL`).bind(r.caller.tokenId).first<Principal>();
  } else {
    c.set('email', r.caller.email);
    principal = await c.env.DB.prepare(`SELECT * FROM todo_principal WHERE auth_email = ? AND disabled_at IS NULL`).bind(r.caller.email).first<Principal>();
  }
  c.set('principal', principal);
  if (!principal && !(c.get('email') && c.req.method === 'POST' && c.req.path.endsWith('/principals'))) {
    return c.json({ error: 'principal is unknown or disabled' }, 403);
  }
  await next();
};
