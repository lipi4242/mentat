// GET /api/local-login/:token — trade a one-time link from `npm run
// login-link` (worker/scripts/lib/login-link.mjs) for a browser session, so
// the owner of a LOCAL admin can sign in without a mailbox or the log.
//
// Why this is safe enough to exist:
// - It only answers on a local admin: OTP_DRY_RUN=1, which sendOtpEmail
//   already refuses on a non-local BETTER_AUTH_URL, AND a loopback request
//   host. A deployed admin answers 404, as if the route did not exist.
// - Making a link needs write access to the local D1 file, i.e. a shell as
//   the admin's own user — who can already read every OTP from the log.
// - The token is 256 random bits, stored only as its SHA-256, valid for 10
//   minutes, and spent by the first request (DELETE … RETURNING, atomic).
// - The session is minted through better-auth itself (a server-only OTP,
//   then the normal OTP sign-in), for an address on ADMIN_EMAILS only.
import type { Hono } from 'hono';
import type { AppEnv } from '../types';
import { adminEmails } from '../types';
import { createAuth } from '../lib/better-auth';
import { isLocalEnv } from '../lib/email';
import { hashToken } from '../lib/tokens';

const PREFIX = 'local-login:';
const LOOPBACK = new Set(['localhost', '127.0.0.1', '[::1]']);

const page = (msg: string) =>
  `<!doctype html><meta charset="utf-8"><title>Belépés</title><p style="font-family:sans-serif;margin:2rem">${msg}</p>`;

export function registerLocalLoginRoutes(app: Hono<AppEnv>) {
  app.get('/api/local-login/:token', async (c) => {
    const local = c.env.OTP_DRY_RUN === '1' && isLocalEnv(c.env) && LOOPBACK.has(new URL(c.req.url).hostname);
    if (!local) return c.json({ error: 'not found' }, 404);
    if (!c.env.BETTER_AUTH_SECRET) return c.json({ error: 'auth not configured' }, 503);

    const hash = await hashToken(c.req.param('token'));
    const row = await c.env.DB.prepare(
      `DELETE FROM auth_verification WHERE identifier = ?1 RETURNING value, expiresAt`,
    )
      .bind(PREFIX + hash)
      .first<{ value: string; expiresAt: number }>();
    if (!row || row.expiresAt <= Date.now()) {
      return c.html(page('Ez a belépő link lejárt vagy már felhasználták. Kérj újat: <code>npm run login-link</code>'), 410);
    }
    const email = row.value.toLowerCase();
    if (!adminEmails(c.env).includes(email)) {
      return c.html(page(`A(z) ${email} cím nem léphet be ide (ADMIN_EMAILS).`), 403);
    }

    const auth = createAuth(c.env);
    const otp = await auth.api.createVerificationOTP({ body: { email, type: 'sign-in' } });
    const { headers } = await auth.api.signInEmailOTP({ body: { email, otp }, returnHeaders: true });
    const res = c.redirect('/', 302);
    for (const cookie of headers.getSetCookie()) res.headers.append('set-cookie', cookie);
    return res;
  });
}
