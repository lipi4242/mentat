// Which token a connected repo should hold, and the swap when it changes.
// A token is kept only while it works AND its scopes cover every plugin the
// repo uses (what it had + what was asked). Otherwise a new one is minted and
// written, proven to answer, and only then is the old one revoked; if the new
// one does not answer, the old one goes back into .env, untouched.
// With todo, the agent's principal follows the token (remapped on a swap,
// created on first use) and its handle goes to mentat.json
// components.admin.todo_handle, so `todo me` needs no --as and no manual step.
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { envValue } from './agent-setup.mjs';
import { upsertEnv } from './connect.mjs';
import { mergeSection, readJson, withLock, writeJsonAtomic } from './manifest.mjs';
import { revoke } from './mint.mjs';
import { parseSeed, seedPrincipals } from './seed-principals.mjs';

const SCOPE = { cases: 'cases:write', todo: 'todo:write' };
const q = (v) => `'${String(v).replace(/'/g, "''")}'`;

/** What the repo already uses (an admin section without plugins = cases) plus what was asked. */
export function pluginsFor(doc, asked) {
  const admin = doc?.components?.admin;
  const had = admin ? admin.plugins ?? ['cases'] : [];
  const all = [...new Set([...had, ...(asked ?? (admin ? [] : ['cases']))])];
  return all.length ? all : ['cases'];
}

export const neededScopes = (plugins) => [...new Set(plugins.map((p) => SCOPE[p]).filter(Boolean))].join(' ') || 'cases:write';
const covers = (have, need) => need.split(' ').every((s) => have.split(' ').includes(s));

/** The live row of a plaintext token (looked up by its hash), or null. */
async function tokenRow(query, plain) {
  if (!plain) return null;
  const hash = createHash('sha256').update(plain).digest('hex');
  const [rows] = await query([
    `SELECT id, label, scopes FROM agent_token WHERE token_hash = ${q(hash)} AND active = 1 AND unixepoch(expires_at) > unixepoch('now')`,
  ]);
  return rows[0] ?? null;
}

/** Move the old token's principal to the new token, or create one; → its handle. */
async function agentPrincipal(query, { oldId, id, label, handle }) {
  const pick = async () => (await query([`SELECT handle FROM todo_principal WHERE agent_token_id = ${q(id)}`]))[0][0]?.handle;
  if (oldId) await query([`UPDATE todo_principal SET agent_token_id = ${q(id)} WHERE agent_token_id = ${q(oldId)} AND kind = 'agent'`]);
  const found = await pick();
  if (found) return found;
  const { report } = await seedPrincipals(query, parseSeed({ agents: [{ name: label, ...(handle ? { handle } : {}) }] }));
  if (!report[0].ok) throw new Error(`todo principal for "${label}": ${report[0].status} — rerun with --handle <name>`);
  return pick();
}

/**
 * `connectFn(scopes, plugins)` mints and binds (scripts/lib/connect.mjs);
 * `works(token)` asks the admin whether it accepts it. → {kept} | {minted, revoked}, plus handle.
 */
export async function bindToken({ query, repo, tokenEnv, asked, scope, handle, works, connectFn }) {
  const doc = readJson(join(repo, 'mentat.json'));
  const plugins = pluginsFor(doc, asked);
  const need = scope ?? neededScopes(plugins);
  const oldPlain = envValue(repo, tokenEnv);
  const old = await tokenRow(query, oldPlain);
  let out = { revoked: [] };
  let tokenId = old?.id;
  let label = old?.label;
  if (old && doc?.components?.admin && covers(old.scopes, need) && (await works(oldPlain))) {
    out.kept = old;
  } else {
    const minted = await connectFn(need, plugins);
    if (!(await works(envValue(repo, tokenEnv)))) {
      if (oldPlain) upsertEnv(join(repo, '.env'), tokenEnv, oldPlain);
      await revoke(query, { id: minted.id });
      throw new Error(`the new token ${minted.id} did not work; it is revoked, ${oldPlain ? 'the old one is back in .env, ' : ''}nothing of the old one was revoked`);
    }
    out = { minted, revoked: old ? await revoke(query, { id: old.id }) : [] };
    ({ id: tokenId, label } = minted);
  }
  if (plugins.includes('todo')) {
    const h = await agentPrincipal(query, { oldId: out.minted ? old?.id : undefined, id: tokenId, label, handle });
    await withLock(repo, async () => {
      const cur = readJson(join(repo, 'mentat.json'));
      writeJsonAtomic(join(repo, 'mentat.json'), mergeSection(cur, ['components', 'admin'], { plugins, todo_handle: h }));
    });
    out.handle = h;
  }
  return out;
}
