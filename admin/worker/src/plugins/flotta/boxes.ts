// Box-regisztráció és a box-token. A token ugyanúgy készül, mint a többi gépi
// token (core agent_token, csak a hash tárolódik, a nyílt érték egyszer, a
// válaszban látszik), de a jogköre PONTOSAN `flotta:report`, és egy boxhoz kötött.
// Csak admin-session: gépi token nem regisztrálhat boxot és nem forgathat tokent.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireAdmin } from '../../lib/guards';
import { DEFAULT_DAYS, expiryFrom, newToken } from '../../lib/token-rules.mjs';
import { newId } from '../todo/id';
import { DEFAULT_FLEET, getFleet, iso, Problem, REPORT_SCOPE, type Box } from './types';
import { NAME_RE } from './validate';
import { resolveWhere } from './incidents';

async function mint(db: D1Database, name: string, days: number) {
  const { id, plain, hash } = await newToken();
  const expires_at = expiryFrom(new Date(), days);
  await db.prepare('INSERT INTO agent_token (id, label, token_hash, scopes, expires_at) VALUES (?1, ?2, ?3, ?4, ?5)')
    .bind(id, `box-${name}`, hash, REPORT_SCOPE, expires_at).run();
  return { token_id: id, token: plain, expires_at };
}

async function bindable(db: D1Database, tokenId: string) {
  const t = await db.prepare(`SELECT scopes FROM agent_token WHERE id = ?1 AND active = 1 AND unixepoch(expires_at) > unixepoch('now')`)
    .bind(tokenId).first<{ scopes: string }>();
  if (!t) throw new Problem('token_id must name a live token');
  if (t.scopes.trim() !== REPORT_SCOPE) throw new Problem(`a box token must have exactly the ${REPORT_SCOPE} scope (least privilege)`);
  if (await db.prepare('SELECT 1 FROM flotta_box WHERE token_id = ?1').bind(tokenId).first()) throw new Problem('token already bound to a box', 409);
}

/** A box-token élettartama (AD-11): alapból 90 nap, legfeljebb 180; a forgatás a
 *  POST /boxes/:name/token. A lejárt token = a box néma → dead-man incidens, nem csend. */
export const BOX_MAX_DAYS = 180;
const days = (v: unknown) => {
  const n = v === undefined ? DEFAULT_DAYS : v;
  if (!Number.isInteger(n) || (n as number) < 1 || (n as number) > BOX_MAX_DAYS) throw new Problem(`days must be 1–${BOX_MAX_DAYS}`, 400);
  return n as number;
};

export function registerBoxes(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/boxes', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const body = await c.req.json().catch(() => null) as Record<string, unknown> | null;
    const name = typeof body?.name === 'string' ? body.name : '';
    if (!NAME_RE.test(name)) throw new Problem('name must be a box name ([A-Za-z0-9._-], as in the fleet registry)', 400);
    const fleetId = typeof body?.fleet_id === 'string' ? body.fleet_id : DEFAULT_FLEET;
    const kind = body?.kind === undefined ? 'box' : body.kind;   // 'desktop': saját gép, nincs dead-man (paritás)
    if (kind !== 'box' && kind !== 'desktop') throw new Problem('kind must be box or desktop', 400);
    if (!await getFleet(c.env.DB, fleetId)) throw new Problem('unknown fleet', 404);
    if (await c.env.DB.prepare('SELECT 1 FROM flotta_box WHERE name = ?1').bind(name).first()) throw new Problem('box already registered', 409);
    let minted: { token_id: string; token?: string; expires_at?: string };
    if (typeof body?.token_id === 'string') { await bindable(c.env.DB, body.token_id); minted = { token_id: body.token_id }; }
    else minted = await mint(c.env.DB, name, days(body?.days));
    const id = newId();
    await c.env.DB.prepare('INSERT INTO flotta_box (id, fleet_id, name, token_id, created_at, kind) VALUES (?1, ?2, ?3, ?4, ?5, ?6)')
      .bind(id, fleetId, name, minted.token_id, iso(new Date()), kind).run();
    return c.json({ id, name, fleet_id: fleetId, kind, ...minted }, 201);
  });

  // Forgatás: új token, a régi azonnal visszavonva.
  app.post('/api/flotta/v1/boxes/:name/token', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const box = await c.env.DB.prepare('SELECT * FROM flotta_box WHERE name = ?1').bind(c.req.param('name')).first<Box>();
    if (!box) throw new Problem('box not found', 404);
    const body = await c.req.json().catch(() => ({})) as Record<string, unknown>;
    const fresh = await mint(c.env.DB, box.name, days(body.days));
    await c.env.DB.batch([
      c.env.DB.prepare('UPDATE flotta_box SET token_id = ?1 WHERE id = ?2').bind(fresh.token_id, box.id),
      c.env.DB.prepare('UPDATE agent_token SET active = 0 WHERE id = ?1').bind(box.token_id),
    ]);
    return c.json({ name: box.name, ...fresh });
  });

  // Kivezetett box: nem jelenthet, és nem nyit dead-man incidenst.
  app.post('/api/flotta/v1/boxes/:name/disable', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const box = await c.env.DB.prepare('SELECT * FROM flotta_box WHERE name = ?1 AND disabled_at IS NULL').bind(c.req.param('name')).first<Box>();
    if (!box) throw new Problem('box not found or already disabled', 404);
    const at = new Date();
    // a kivezetett box tokenje azonnal visszavonva (AD-11), nem csak a box-sor tiltva
    await c.env.DB.batch([
      c.env.DB.prepare('UPDATE flotta_box SET disabled_at = ?1 WHERE id = ?2').bind(iso(at), box.id),
      c.env.DB.prepare('UPDATE agent_token SET active = 0 WHERE id = ?1').bind(box.token_id),
    ]);
    await resolveWhere(c.env.DB, box.id, () => true, 'a box kivezetve', at);   // a box és minden ágense
    return c.json({ name: box.name, disabled: true });
  });

  // Ágens áthelyezése másik boxra: az admin felszabadítja; a nyitott incidensei lezárulnak,
  // és a következő jelentő box veszi fel. Box-token ezt nem teheti (a jelentés 409-et kap).
  app.post('/api/flotta/v1/agents/:name/release', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const db = c.env.DB, name = c.req.param('name');
    const agent = await db.prepare('SELECT * FROM flotta_agent WHERE name = ?1').bind(name).first<{ id: string; box_id: string }>();
    if (!agent) throw new Problem('agent not found', 404);
    const closed = await resolveWhere(db, agent.box_id, inc => inc.agent === name, 'az ágens áthelyezésre felszabadítva', new Date());
    await db.prepare('DELETE FROM flotta_agent WHERE id = ?1').bind(agent.id).run();
    return c.json({ name, released: true, resolved: closed.length });
  });
}
