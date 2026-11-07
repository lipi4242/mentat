// Mint and revoke agent tokens straight in D1 (CLI side of src/core/tokens.ts).
//
// SQL SAFETY. `wrangler d1 execute` takes SQL as text only; it cannot bind
// parameters, so values are inlined. They are validated first (checkMint:
// strict allowlists for label and scopes, an integer for days) and only then
// single-quote-escaped; id, hash and expiry are generated here. The plaintext
// token is never part of the SQL, an argv or a file written by this module.
import { LABEL_RE, checkMint, expiryFrom, newToken } from '../../src/lib/token-rules.mjs';

const q = (v) => `'${String(v).replace(/'/g, "''")}'`;

/** Validate a mint request. Throws on an invalid one. */
export function checkRequest(request) {
  const req = checkMint(request);
  if ('error' in req) throw new Error(req.error);
  return req;
}

/**
 * The INSERT for a token made elsewhere — here (prepareMint) or on the box
 * that will hold it (mint-on.mjs). Only the id and the hash come in.
 */
export function buildMint(request, { id, hash }, now = new Date()) {
  const req = checkRequest(request);
  if (!/^[0-9a-f]{64}$/.test(hash) || !/^[0-9a-f-]{36}$/.test(id)) throw new Error('internal: bad id or hash');
  const expires_at = expiryFrom(now, req.days);
  const sql =
    `INSERT INTO agent_token (id, label, token_hash, scopes, expires_at) VALUES ` +
    `(${q(id)}, ${q(req.label)}, ${q(hash)}, ${q(req.scopes)}, ${q(expires_at)})`;
  return { id, label: req.label, scopes: req.scopes, expires_at, sql };
}

/** Validate, then build the INSERT. Throws on an invalid request. */
export async function prepareMint(request, now = new Date()) {
  checkRequest(request);
  const { id, plain, hash } = await newToken();
  const m = buildMint(request, { id, hash }, now);
  return { ...m, token: plain };
}

/** Mint through `queryMany` (scripts/lib/d1.mjs). Returns the token once. */
export async function mint(queryMany, request) {
  const m = await prepareMint(request);
  await queryMany([m.sql]);
  const { sql: _sql, ...minted } = m;
  return minted;
}

/** Deactivate by id or by agent label. Returns the ids revoked. */
export async function revoke(queryMany, { id, label }) {
  if (!!id === !!label) throw new Error('give exactly one of --id or --agent');
  if (id && !/^[0-9a-f-]{36}$/.test(id)) throw new Error('--id must be a token id (uuid)');
  if (label && !LABEL_RE.test(label)) throw new Error('--agent is not a valid label');
  const where = id ? `id = ${q(id)}` : `label = ${q(label)}`;
  const [rows] = await queryMany([`UPDATE agent_token SET active = 0 WHERE ${where} AND active = 1 RETURNING id`]);
  return rows.map((r) => r.id);
}

/** Deactivate every active token of an agent label except `keep` (the one just minted). */
export async function revokeOthers(queryMany, { label, keep }) {
  if (!LABEL_RE.test(label) || !/^[0-9a-f-]{36}$/.test(keep)) throw new Error('revokeOthers: bad label or id');
  const [rows] = await queryMany([`UPDATE agent_token SET active = 0 WHERE label = ${q(label)} AND id != ${q(keep)} AND active = 1 RETURNING id`]);
  return rows.map((r) => r.id);
}
