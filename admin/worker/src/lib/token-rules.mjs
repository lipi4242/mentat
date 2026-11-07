// Agent-token rules shared by the worker (admin UI route) and the CLI
// (scripts/mint-token.mjs, scripts/connect.mjs) — one definition of what a
// valid label, scope list and lifetime is, and of how a token is made.
// Plain JS on purpose: the CLI runs it on a bare Node without a TS step.

/** A label names the agent: an operator-facing name, not free text. */
export const LABEL_RE = /^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$/;
/** Whitespace-separated `resource:action` tokens (see guards.ts hasScope). */
export const SCOPE_RE = /^[a-z0-9_-]+:[a-z0-9_-]+$/;
/** Every token expires. A year is the ceiling; rotation is the way past it. */
export const MAX_DAYS = 365;
export const DEFAULT_DAYS = 90;

/**
 * Validate a mint request. `scopes` may be a string (space or comma
 * separated) or an array. Returns the normalized request or an error message.
 */
export function checkMint({ label, scopes, days = DEFAULT_DAYS }) {
  if (typeof label !== 'string' || !LABEL_RE.test(label)) {
    return { error: 'label must be 1-64 chars of [A-Za-z0-9 ._@-] and start alphanumeric' };
  }
  const list = (Array.isArray(scopes) ? scopes : String(scopes ?? '').split(/[\s,]+/)).filter(Boolean);
  if (!list.length) return { error: 'at least one scope is required' };
  const bad = list.find((s) => typeof s !== 'string' || !SCOPE_RE.test(s));
  if (bad !== undefined) return { error: `invalid scope ${JSON.stringify(bad)} (expected resource:action)` };
  const n = typeof days === 'string' && /^[0-9]+$/.test(days) ? Number(days) : days;
  if (!Number.isInteger(n) || n < 1 || n > MAX_DAYS) return { error: `days must be an integer between 1 and ${MAX_DAYS}` };
  return { label, scopes: [...new Set(list)].join(' '), days: n };
}

/** `YYYY-MM-DD HH:MM:SS` UTC — the same form datetime('now') writes. */
export function expiryFrom(now, days) {
  return new Date(now.getTime() + days * 86400000).toISOString().slice(0, 19).replace('T', ' ');
}

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');

/** A fresh token: the plaintext (shown once) and the hash (the only thing stored). */
export async function newToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const b64 = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const plain = `mentat_${b64}`;
  const hash = hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(plain)));
  return { id: crypto.randomUUID(), plain, hash };
}
