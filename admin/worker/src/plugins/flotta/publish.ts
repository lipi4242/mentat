// PUT /api/flotta/v1/managers — a menedzser-lista EGYETLEN írója (flotta-menedzser). Forrása a
// verziózott `fleet-ops/fleet/managers.json`, kiadója a `fleet managers publish`, egy KÜLÖN,
// pontosan `flotta:config` jogkörű tokennel. A box jelentő tokenje (flotta:report) nem írhat
// konfigurációt: az a tokent, amelyben a report jog is benne van, elutasítjuk.
// Régebbi verzió → 409; ugyanaz a verzió más tartalommal → 409; ugyanaz a tartalom → no-op.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { hasScope, resolveAgentToken } from '../../lib/guards';
import { hashToken } from '../../lib/tokens';
import { newId } from '../todo/id';
import { CONFIG_SCOPE, DEFAULT_FLEET, getFleet, iso, Problem, REPORT_SCOPE } from './types';
import { NAME_RE } from './validate';

const MAX = 50;
export const SCOPE_RE = /^(\*|(agent|box):[A-Za-z0-9][A-Za-z0-9._-]{0,63})$/;
type In = { handle: string; agent: string; scope: string; rank: number };

export function parseManagers(input: unknown): In[] {
  if (!Array.isArray(input) || input.length > MAX) throw new Problem(`managers must be a list up to ${MAX}`, 400);
  const out: In[] = [];
  for (const [i, raw] of input.entries()) {
    const m = (raw ?? {}) as Record<string, unknown>;
    const handle = m.handle, agent = m.agent ?? m.handle, scope = m.scope, rank = m.rank;
    if (typeof handle !== 'string' || !NAME_RE.test(handle)) throw new Problem(`managers[${i}].handle must be a todo handle`, 400);
    if (typeof agent !== 'string' || !NAME_RE.test(agent)) throw new Problem(`managers[${i}].agent must be a fleet agent name`, 400);
    if (typeof scope !== 'string' || !SCOPE_RE.test(scope)) throw new Problem(`managers[${i}].scope must be *, agent:<name> or box:<name>`, 400);
    if (!Number.isInteger(rank) || (rank as number) < 1 || (rank as number) > 1000) throw new Problem(`managers[${i}].rank must be a positive integer`, 400);
    if (out.some(x => x.handle === handle && x.scope === scope)) throw new Problem(`managers[${i}]: duplicate (handle, scope)`, 400);
    out.push({ handle, agent, scope, rank: rank as number });
  }
  return out;
}

/** A tartalom ujjlenyomata sorrendfüggetlenül: ugyanaz a lista ugyanazt adja. */
export const digest = (list: In[]) =>
  hashToken(JSON.stringify([...list].sort((a, b) => `${a.scope}|${a.rank}|${a.handle}`.localeCompare(`${b.scope}|${b.rank}|${b.handle}`))));

export function registerPublish(app: Hono<AppEnv>) {
  app.put('/api/flotta/v1/managers', async c => {
    const tok = await resolveAgentToken(c.env.DB, c.req.header('X-Mentat-Token') ?? '');
    if (!tok) throw new Problem('unauthorized', 401);
    if (!hasScope(tok.scopes, CONFIG_SCOPE)) throw new Problem(`forbidden: needs ${CONFIG_SCOPE}`, 403);
    // pontosan ez az egy jogkör (mint a box-tokennél): egy kiadó-token mással nem keveredhet
    if (tok.scopes.trim() !== CONFIG_SCOPE) throw new Problem(`the publisher token must have exactly the ${CONFIG_SCOPE} scope (not ${REPORT_SCOPE} or others)`, 403);
    const body = await c.req.json().catch(() => null) as Record<string, unknown> | null;
    const version = body?.version;
    if (!Number.isInteger(version) || (version as number) < 1) throw new Problem('version must be a positive integer', 400);
    const fleetId = body?.fleet === undefined ? DEFAULT_FLEET : body.fleet;
    if (typeof fleetId !== 'string') throw new Problem('fleet must be a fleet id', 400);
    const db = c.env.DB, fleet = await getFleet(db, fleetId);
    if (!fleet) throw new Problem('unknown fleet', 404);
    const list = parseManagers(body?.managers);
    const dig = await digest(list);
    const stored = fleet.managers_digest?.split(':')[0] ?? null;   // tárolva: '<tartalom-hash>:<kiadás-jel>'
    if ((version as number) < fleet.managers_version || ((version as number) === fleet.managers_version && dig !== stored)) {
      return c.json({ error: 'stale version', code: 'stale', current: fleet.managers_version }, 409);
    }
    if ((version as number) === fleet.managers_version) return c.json({ version, unchanged: true, managers: list });
    const rows = [];
    for (const [i, m] of list.entries()) {
      const p = await db.prepare('SELECT id, kind FROM todo_principal WHERE handle = ?1 AND disabled_at IS NULL').bind(m.handle).first<{ id: string; kind: string }>();
      if (!p) throw new Problem(`managers[${i}]: ${m.handle} is not an enabled todo principal`);
      if (p.kind !== 'agent') throw new Problem(`managers[${i}]: a manager must be an agent principal`);
      rows.push({ ...m, principal_id: p.id });
    }
    const now = iso(new Date()), mark = `${dig}:${newId()}`;
    // CAS a verzióra: két egyidejű kiadásból egy nyer, a másik 409; a sorokat CSAK a nyertes (a saját jele) írja
    const [cas] = await db.batch([
      db.prepare('UPDATE flotta_fleet SET managers_version = ?1, managers_digest = ?2, updated_at = ?3 WHERE id = ?4 AND managers_version = ?5')
        .bind(version, mark, now, fleet.id, fleet.managers_version),
      db.prepare('DELETE FROM flotta_manager WHERE fleet_id = ?1 AND EXISTS (SELECT 1 FROM flotta_fleet WHERE id = ?1 AND managers_version = ?2 AND managers_digest = ?3)')
        .bind(fleet.id, version, mark),
      ...rows.map(m => db.prepare(`INSERT INTO flotta_manager (id, fleet_id, principal_id, agent, scope, rank, created_at)
          SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7 WHERE EXISTS (SELECT 1 FROM flotta_fleet WHERE id = ?2 AND managers_version = ?8 AND managers_digest = ?9)`)
        .bind(newId(), fleet.id, m.principal_id, m.agent, m.scope, m.rank, now, version, mark)),
    ]);
    if (cas.meta.changes !== 1) return c.json({ error: 'stale version', code: 'stale' }, 409);
    return c.json({ version, unchanged: false, managers: list });
  });
}
