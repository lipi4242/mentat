import type { Context } from 'hono';
import type { AppEnv, Env } from '../types';
import { adminEmails } from '../types';
import { createAuth } from './better-auth';
import { hashToken } from './tokens';

export type AgentToken = { id: string; label: string; scopes: string };

/**
 * Exact, whole-token scope match. `agent_token.scopes` is a whitespace
 * separated list, and the comparison MUST split on whitespace — a naive
 * `scopes.includes('cases:write')` false-positives on
 * 'cases:writeall'. Never substring, never LIKE.
 */
export function hasScope(scopes: string, need: string): boolean {
  if (!need) return false;
  return scopes.split(/\s+/).filter(Boolean).includes(need);
}

/**
 * Look a bearer-style machine token up by hash. Returns null for unknown,
 * inactive and expired tokens alike — the caller cannot tell which, so a
 * probing client learns nothing.
 *
 * Liveness is decided in SQL, on purpose. Doing it in JS fails OPEN twice
 * over: `new Date('garbage').getTime()` is NaN and `NaN < Date.now()` is
 * false (garbage accepted), and an empty string satisfies TEXT NOT NULL but
 * is falsy, so a `row.expires_at &&` guard skips the check entirely (token
 * never expires). `unixepoch()` returns NULL for anything it cannot parse,
 * and NULL > NULL is not true, so both cases exclude the row. It also
 * accepts both the ISO `...Z` form and the `datetime('now')` space form, and
 * avoids `new Date('2026-07-28 00:00:00')` being read as LOCAL time — worth
 * up to ~14h of extra life on a non-UTC runtime.
 *
 * The mint script's input validation is not a substitute: writing rows by
 * hand with `wrangler d1 execute` is a documented workflow, so this guard
 * has to hold whoever wrote the row.
 */
export async function resolveAgentToken(DB: Env['DB'], plain: string): Promise<AgentToken | null> {
  if (!plain) return null;
  const hash = await hashToken(plain);
  const row = await DB.prepare(
    `SELECT id, label, scopes FROM agent_token
      WHERE token_hash = ?1 AND active = 1 AND unixepoch(expires_at) > unixepoch('now')`,
  )
    .bind(hash)
    .first<{ id: string; label: string; scopes: string }>();
  if (!row) return null;
  // last_used_at is telemetry, not a security control. A transient write
  // failure must not turn a fully authorized request into a 500.
  try {
    await DB.prepare(`UPDATE agent_token SET last_used_at = datetime('now') WHERE id = ?1`).bind(row.id).run();
  } catch (err) {
    console.error('agent_token last_used_at update failed', err);
  }
  return { id: row.id, label: row.label, scopes: row.scopes };
}

/** The signed-in admin's lower-cased e-mail, or null (no secret, no session, not on ADMIN_EMAILS). */
export async function adminSessionEmail<E extends AppEnv>(c: Context<E>): Promise<string | null> {
  if (!c.env.BETTER_AUTH_SECRET) return null;
  try {
    const session = await createAuth(c.env).api.getSession({ headers: c.req.raw.headers });
    const email = session?.user?.email?.toLowerCase();
    return email && adminEmails(c.env).includes(email) ? email : null;
  } catch {
    return null;
  }
}

export async function hasAdminSession<E extends AppEnv>(c: Context<E>): Promise<boolean> {
  return (await adminSessionEmail(c)) !== null;
}

/** Browser-only surface (settings, token administration). Never a machine token. */
export async function requireAdmin<E extends AppEnv>(c: Context<E>): Promise<Response | null> {
  return (await hasAdminSession(c)) ? null : c.json({ error: 'unauthorized' }, 401);
}

export type Caller = { kind: 'agent'; tokenId: string; scopes: string } | { kind: 'user'; email: string };

/**
 * Read or write on a data route: the human session, or an agent token that
 * actually holds the scope. The scope check exists from day one — retrofitting
 * authorization onto a live API is how gaps happen. Every plugin decides here,
 * so a bad token answers the same everywhere (401) and a fix lands once.
 *
 * On success, `c.set('actor', ...)` carries who it was into the event trail,
 * and the returned caller tells a plugin whom to map (token id or e-mail).
 */
export async function authorize<E extends AppEnv>(
  c: Context<E>,
  scope: string | readonly string[],
): Promise<{ denied: Response } | { caller: Caller }> {
  // Any one of a list will do — e.g. a read that `cases:read` OR
  // `cases:write` satisfies. Each candidate is still an exact-token match.
  const any = typeof scope === 'string' ? [scope] : scope;
  const supplied = c.req.header('X-Mentat-Token');
  const ctx = c as unknown as Context<AppEnv>;
  // Precedence is deliberate and total: if a token header is present — even
  // an empty one — it decides the request outright, with no fallback to the
  // session cookie. A request carrying a valid cookie AND a bad token gets
  // 401, not a silent downgrade to the human identity — the caller asked to
  // act as the agent.
  if (supplied !== undefined) {
    const tok = await resolveAgentToken(c.env.DB, supplied);
    if (!tok) return { denied: c.json({ error: 'unauthorized' }, 401) };
    if (!any.some((s) => hasScope(tok.scopes, s))) return { denied: c.json({ error: 'forbidden', need: any.join(' | ') }, 403) };
    ctx.set('actor', { actor: 'agent' as const, actorTokenId: tok.id });
    return { caller: { kind: 'agent', tokenId: tok.id, scopes: tok.scopes } };
  }
  const email = await adminSessionEmail(c);
  if (email) {
    ctx.set('actor', { actor: 'user' as const, actorTokenId: null });
    return { caller: { kind: 'user', email } };
  }
  return { denied: c.json({ error: 'unauthorized' }, 401) };
}

export async function requireWriter<E extends AppEnv>(c: Context<E>, scope: string | readonly string[]): Promise<Response | null> {
  const r = await authorize(c, scope);
  return 'denied' in r ? r.denied : null;
}
