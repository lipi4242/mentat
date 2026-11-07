import type { Hono } from 'hono';
import type { AppEnv } from '../types';
import { requireAdmin } from '../lib/guards';
import { checkMint, expiryFrom, newToken } from '../lib/token-rules.mjs';

/**
 * Agent-token administration for the admin UI. Session only (requireAdmin):
 * a machine token must never be able to mint or revoke tokens, whatever its
 * scopes say. The plaintext exists in exactly one place — the mint response;
 * the table holds the hash (see migrations/0002_core.sql).
 */
export function registerTokenRoutes(app: Hono<AppEnv>) {
  app.get('/api/tokens', async (c) => {
    const denied = await requireAdmin(c);
    if (denied) return denied;
    const { results } = await c.env.DB.prepare(
      `SELECT id, label, scopes, active, expires_at, created_at, last_used_at
         FROM agent_token ORDER BY active DESC, created_at DESC`,
    ).all();
    return c.json(results, 200, { 'X-Total-Count': String(results.length) });
  });

  app.post('/api/tokens', async (c) => {
    const denied = await requireAdmin(c);
    if (denied) return denied;
    const body = await c.req.json().catch(() => null);
    if (!body || typeof body !== 'object') return c.json({ error: 'invalid body' }, 400);
    const req = checkMint(body as { label: unknown; scopes: unknown; days?: unknown });
    if ('error' in req) return c.json({ error: req.error }, 400);
    const { id, plain, hash } = await newToken();
    const expires_at = expiryFrom(new Date(), req.days);
    await c.env.DB.prepare(
      `INSERT INTO agent_token (id, label, token_hash, scopes, expires_at) VALUES (?1, ?2, ?3, ?4, ?5)`,
    )
      .bind(id, req.label, hash, req.scopes, expires_at)
      .run();
    return c.json({ id, label: req.label, scopes: req.scopes, expires_at, token: plain });
  });

  app.post('/api/tokens/:id/revoke', async (c) => {
    const denied = await requireAdmin(c);
    if (denied) return denied;
    const res = await c.env.DB.prepare(`UPDATE agent_token SET active = 0 WHERE id = ?1`).bind(c.req.param('id')).run();
    if (!res.meta.changes) return c.json({ error: 'not found' }, 404);
    return c.json({ id: c.req.param('id'), active: 0 });
  });
}
