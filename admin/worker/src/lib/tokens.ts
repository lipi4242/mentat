/** SHA-256 hex. WebCrypto is available in Workers and in Node 18+. */
export async function hashToken(plain: string): Promise<string> {
  const bytes = new TextEncoder().encode(plain);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// No constant-time compare here, deliberately. Token lookup is
// `WHERE token_hash = ?` on a UNIQUE index over the SHA-256 of caller-supplied
// input: an attacker cannot walk it prefix by prefix, because changing one
// byte of the guess changes the whole digest. There is nothing for a
// constant-time comparison to protect, and an exported, unused crypto helper
// is an invitation to misapply it somewhere it does not fit.
