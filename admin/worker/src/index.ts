import { Hono } from 'hono';
import { cors } from 'hono/cors';
import type { AppEnv, Env } from './types';
import { createAuth } from './lib/better-auth';
import { registerTokenRoutes } from './core/tokens';
import { registerLocalLoginRoutes } from './core/local-login';
import type { AdminPlugin } from './core/plugin';
import { PLUGINS } from '../../config/plugins';

/** The whole API for a plugin list — the deployed one below, or a test's own. */
export function createApp(plugins: AdminPlugin[]) {
  const app = new Hono<AppEnv>();

  app.use('*', async (c, next) => {
    const allowed = (c.env.ALLOWED_ORIGINS ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const mw = cors({
      origin: (origin) => (allowed.includes(origin) ? origin : ''),
      allowMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
      allowHeaders: ['Content-Type', 'X-Mentat-Token', 'If-Match'],
      credentials: true,
      maxAge: 86400,
    });
    return mw(c, next);
  });

  app.get('/api/health', (c) => c.json({ ok: true, service: 'mentat-admin' }));

  // better-auth (email OTP): /api/auth/*
  // Note there is deliberately no X-Mentat-Token handling here — a machine token
  // must never be able to mint a browser session.
  app.on(['GET', 'POST'], '/api/auth/*', (c) => {
    // Refuse to serve auth at all without a secret. better-auth would otherwise
    // silently fall back to its published default secret and happily issue
    // sessions — while hasAdminSession() fails closed and rejects every one of
    // them. That presents as "login works, then every write 401s", which is
    // miserable to debug. Fail loudly at the door instead.
    if (!c.env.BETTER_AUTH_SECRET) return c.json({ error: 'auth not configured' }, 503);
    return createAuth(c.env).handler(c.req.raw);
  });

  registerLocalLoginRoutes(app);
  registerTokenRoutes(app);

  for (const plugin of plugins) plugin.registerRoutes(app);

  app.notFound((c) => c.json({ error: 'not found' }, 404));
  app.onError((err, c) => {
    console.error('unhandled', err);
    return c.json({ error: 'internal error' }, 500);
  });
  return app;
}

/** Every plugin's cron, in order; one plugin's failure does not stop the next. */
export async function runScheduled(env: Env, plugins: AdminPlugin[], now: Date) {
  for (const plugin of plugins) {
    if (!plugin.scheduled) continue;
    try {
      await plugin.scheduled(env, now);
    } catch (err) {
      console.error('scheduled-failed', plugin.id, err);
    }
  }
}

// The Hono app is the fetch handler; `scheduled` makes the same export the cron
// handler (wrangler.toml [triggers]).
export default Object.assign(createApp(PLUGINS), {
  scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(runScheduled(env, PLUGINS, new Date()));
  },
});
