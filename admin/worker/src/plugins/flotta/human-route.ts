// Emberi átvétel és lezárás (flotta-menedzser), csak admin-sessionnel. Az átvétel minden automatikus
// tokent érvénytelenít (új fence); ha épp fut egy művelet, előbb az zárul le (vagy a zára
// lejár) — addig `drain = 'human'`, és új lépés nem indulhat. A kézi lezárás csak akkor
// megy, ha nincs futó művelet.
import type { Context, Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireAdmin } from '../../lib/guards';
import { createAuth } from '../../lib/better-auth';
import { advance, runningOp } from './assign';
import { CLAIMED, move, type State } from './states';
import { getFleet, iso, Problem, type Incident } from './types';

const who = async (c: Context<AppEnv>) => {
  const s = await createAuth(c.env).api.getSession({ headers: c.req.raw.headers }).catch(() => null);
  return s?.user?.email?.toLowerCase() ?? 'admin';
};

/** Átvétel: fence nélküli állapotból azonnal ember-kell; átvett incidensnél előbb drain. */
function takeover(inc: Incident, by: string): { to: State; set: Record<string, string | number | null> } {
  const kill = { fence: inc.fence + 1, claim_hash: null, nonce_hash: null, nonce_fence: null, human_by: by, human_reason: 'emberi átvétel' };
  if (CLAIMED.includes(inc.state as State)) return { to: inc.state as State, set: { drain: 'human', human_by: by, human_reason: 'emberi átvétel' } };
  if (inc.state === 'ember-kell') return { to: 'ember-kell', set: kill };
  return { to: 'ember-kell', set: { ...kill, assigned_principal_id: null } };
}

export function registerHuman(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/incidents/:id/human-claim', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const db = c.env.DB, now = new Date();
    const inc = await db.prepare('SELECT * FROM flotta_incident WHERE id = ?1').bind(c.req.param('id')).first<Incident>();
    if (!inc) throw new Problem('incident not found', 404);
    if (inc.state === 'megoldva') throw new Problem('incident already resolved', 409, 'state');
    const by = await who(c);
    // a drain azonnal tilt minden új lépést; az átmenetet az advance (most vagy a cron) végzi el
    const t = takeover(inc, await who(c));
    if (!await move(db, inc, t.to, now, t.set, { kind: 'human_claim_requested' })) throw new Problem('the incident changed meanwhile', 409, 'cas');
    await advance(db, (await getFleet(db, inc.fleet_id))!, now, inc.id);
    const after = await db.prepare('SELECT state, drain FROM flotta_incident WHERE id = ?1').bind(inc.id).first<{ state: string; drain: string | null }>();
    return c.json({ state: after!.state, draining: after!.drain === 'human' }, after!.drain ? 202 : 200);
  });

  app.post('/api/flotta/v1/incidents/:id/human-resolve', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const db = c.env.DB, now = new Date();
    const inc = await db.prepare('SELECT * FROM flotta_incident WHERE id = ?1').bind(c.req.param('id')).first<Incident>();
    if (!inc) throw new Problem('incident not found', 404);
    if (inc.state !== 'ember-kell') throw new Problem('take the incident over first (human-claim)', 409, 'state');
    if (await runningOp(db, inc.id, now)) throw new Problem('an operation is still running; wait for it', 409, 'open_ops');
    if (!await move(db, inc, 'megoldva', now, { resolve_note: `kézzel lezárva (${await who(c)}, ${iso(now)})` }, { kind: 'human_resolved' })) {
      throw new Problem('the incident changed meanwhile', 409, 'cas');
    }
    return c.json({ state: 'megoldva' });
  });
}
