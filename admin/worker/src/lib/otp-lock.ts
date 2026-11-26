// Per-address lock for the e-mail code sign-in. better-auth (1.7.18) limits
// requests per IP and kills a code after `allowedAttempts`, but a fresh code
// starts a fresh count and every source IP has its own bucket: with many IPs
// the 6-digit code space can be walked overnight. This counts failed sign-ins
// per e-mail address, across IPs and across codes, and refuses every sign-in
// for that address (the right code too) while it is locked.
//
// Storage: a row in better-auth's own `auth_rate_limit` table (no migration);
// the key is a hash of the address, so the table holds no e-mail in clear.
import { APIError, createAuthMiddleware, isAPIError } from 'better-auth/api';
import type { Env } from '../types';
import { adminEmails } from '../types';

export const OTP_LOCK_MAX_FAILS = 10;
export const OTP_LOCK_SECONDS = 15 * 60;
const SIGN_IN = '/sign-in/email-otp';

async function lockKey(email: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(email.trim().toLowerCase()));
  return 'otp-fail:' + [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

type Row = { count: number; lastRequest: number } | null;

async function read(env: Env, key: string): Promise<Row> {
  return env.DB.prepare('SELECT count, lastRequest FROM auth_rate_limit WHERE key = ?1').bind(key).first<Row>();
}

/** Failures in the current window; a window older than the lock length counts as zero. */
function liveCount(row: Row, now: number): number {
  return row && now - row.lastRequest < OTP_LOCK_SECONDS * 1000 ? row.count : 0;
}

export async function isLocked(env: Env, email: string, now = Date.now()): Promise<boolean> {
  return liveCount(await read(env, await lockKey(email)), now) >= OTP_LOCK_MAX_FAILS;
}

export async function recordFailure(env: Env, email: string, now = Date.now()): Promise<void> {
  const key = await lockKey(email);
  const count = liveCount(await read(env, key), now) + 1;
  await env.DB.prepare(
    'INSERT INTO auth_rate_limit (id, key, count, lastRequest) VALUES (?1, ?1, ?2, ?3) ' +
      'ON CONFLICT(id) DO UPDATE SET count = ?2, lastRequest = ?3',
  )
    .bind(key, count, now)
    .run();
}

export async function clearFailures(env: Env, email: string): Promise<void> {
  await env.DB.prepare('DELETE FROM auth_rate_limit WHERE key = ?1').bind(await lockKey(email)).run();
}

function emailOf(ctx: { path?: string; body?: unknown }): string | null {
  const email = (ctx.body as { email?: unknown } | undefined)?.email;
  return ctx.path === SIGN_IN && typeof email === 'string' ? email : null;
}

/**
 * better-auth `hooks` for the code sign-in. Before: an address outside ADMIN_EMAILS gets the same
 * answer as a wrong code and never reaches user creation (no user row is ever made for it); a
 * locked address is refused before the code is even looked at. After: count or clear.
 */
export function otpLockHooks(env: Env) {
  return {
    before: createAuthMiddleware(async (ctx) => {
      const email = emailOf(ctx);
      if (!email) return;
      if (!adminEmails(env).includes(email.trim().toLowerCase())) {
        throw new APIError('BAD_REQUEST', { message: 'Invalid OTP', code: 'INVALID_OTP' });
      }
      if (await isLocked(env, email)) {
        throw new APIError('TOO_MANY_REQUESTS', { message: 'Too many failed attempts, try again later' });
      }
    }),
    after: createAuthMiddleware(async (ctx) => {
      const email = emailOf(ctx);
      if (!email) return;
      if (isAPIError(ctx.context.returned)) await recordFailure(env, email);
      else await clearFailures(env, email);
    }),
  };
}
