// A one-time sign-in link for a LOCAL admin (no mailbox, no log reading).
// The token lives only in the printed URL; the database keeps its SHA-256 in
// better-auth's own verification table (no extra migration), under an
// identifier better-auth never uses. The worker side is src/core/local-login.ts.
import { createHash, randomBytes, randomUUID } from 'node:crypto';

export const IDENTIFIER_PREFIX = 'local-login:';
export const TTL_MINUTES = 10;
// Narrow on purpose: the address goes into SQL text (wrangler d1 execute has
// no bind parameters), so nothing that could close a quote gets through.
const EMAIL_RE = /^[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}$/;

export function checkEmail(raw) {
  const email = String(raw ?? '').trim().toLowerCase();
  if (!EMAIL_RE.test(email)) throw new Error(`not one e-mail address: ${raw}`);
  return email;
}

/** → { url, sql }: run `sql` against the local D1, hand `url` to the owner. */
export function newLink({ origin, email, now = Date.now(), ttlMinutes = TTL_MINUTES }) {
  const addr = checkEmail(email);
  const token = randomBytes(32).toString('base64url');
  const hash = createHash('sha256').update(token).digest('hex');
  const expires = now + ttlMinutes * 60 * 1000;
  return {
    url: `${new URL(origin).origin}/api/local-login/${token}`,
    expires,
    sql: [
      // Spent and stale links do not pile up.
      `DELETE FROM auth_verification WHERE identifier LIKE '${IDENTIFIER_PREFIX}%' AND expiresAt < ${now}`,
      `INSERT INTO auth_verification (id, identifier, value, expiresAt, createdAt, updatedAt) VALUES ` +
        `('${randomUUID()}', '${IDENTIFIER_PREFIX}${hash}', '${addr}', ${expires}, ${now}, ${now})`,
    ],
  };
}
