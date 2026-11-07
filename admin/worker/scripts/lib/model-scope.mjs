// After `model new` the agent's token has to reach the new entity. The old way
// was a hand-made revoke + connect; this does it in the same command: mint a
// token with the old scopes plus the entity's, bind it to the repo (.env), then
// revoke the others. The token itself is never printed.
import { join } from 'node:path';
import { LABEL_RE } from '../../src/lib/token-rules.mjs';
import { connect } from './connect.mjs';
import { readJson } from './manifest.mjs';
import { mint, revokeOthers } from './mint.mjs';

/** cases plus every declared entity, write scope. */
export const scopesFor = (models) => ['cases', ...models.entities.map((e) => e.name)].map((n) => `${n}:write`).join(' ');

/** → { state: 'has' | 'widened' | 'skipped', line }. Never throws: a failure is a line the agent can read. */
export async function widenToken({ repo, url, models, entity, query }) {
  const doc = readJson(join(repo, 'mentat.json'));
  const agent = doc?.agent?.name;
  if (!agent || !LABEL_RE.test(agent)) return { state: 'skipped', line: `token not widened: no agent name in ${repo}/mentat.json` };
  try {
    const [rows] = await query([`SELECT id, scopes FROM agent_token WHERE label = '${agent}' AND active = 1`]);
    const have = rows.flatMap((r) => String(r.scopes).split(/[\s,]+/));
    if (have.includes(`${entity}:write`)) return { state: 'has', line: `token: already reaches ${entity}` };
    const scopes = [...new Set([...have, ...scopesFor(models).split(' ')])].join(' ');
    const local = readJson(join(repo, '.mentat', 'local.json'));
    const out = await connect({
      repo, url, agent, scopes,
      tokenEnv: local?.admin?.token_env ?? 'MENTAT_ADMIN_TOKEN',
      plugins: doc.components?.admin?.plugins,
      mintFn: (req) => mint(query, req),
    });
    const old = await revokeOthers(query, { label: agent, keep: out.id });
    return { state: 'widened', line: `token: widened to ${out.scopes} (new token in ${repo}/.env${old.length ? `, ${old.length} old revoked` : ''}) — no rebind needed` };
  } catch (e) {
    return { state: 'skipped', line: `token NOT widened (${e instanceof Error ? e.message : e}) — by hand: npm run connect -- --repo ${repo} --url ${url} --local --plugins cases --scope "${scopesFor(models).replace(/ /g, ',')}"` };
  }
}
