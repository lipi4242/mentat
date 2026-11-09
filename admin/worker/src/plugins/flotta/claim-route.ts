// Átvétel (flotta-menedzser): a kiosztott menedzser a SAJÁT todo-tokenjével veszi át az incidenst.
// Fix 30 perces kísérleti keret (meghosszabbítás nincs) és egy növekvő fencing-token jár
// vele, plusz egy titok, amit a célboxon a végrehajtó (`fleet repair-exec`) mutat fel.
// A titoknak csak a hash-e tárolódik. Feladás (`release`): átadás a következőnek.
import type { Context, Hono } from 'hono';
import type { AppEnv } from '../../types';
import { hasScope, resolveAgentToken } from '../../lib/guards';
import { hashToken } from '../../lib/tokens';
import { advance } from './assign';
import { chain, facts, targetOf } from './managers';
import { ATTEMPT_MIN, CLAIMED, Conflict, move, OFFERED, plusMin, secret, type State } from './states';
import { getFleet, iso, Problem, type Row } from './types';

const SELECT = 'SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id WHERE i.id = ?1';

/** A todo-token gazdája (ágens-principal). A box- és a config-token itt nem ér semmit. */
async function principalOf(c: Context<AppEnv>) {
  const tok = await resolveAgentToken(c.env.DB, c.req.header('X-Mentat-Token') ?? '');
  if (!tok) throw new Problem('unauthorized', 401);
  if (!hasScope(tok.scopes, 'todo:write') && !hasScope(tok.scopes, 'flotta:manage')) throw new Problem('forbidden: needs todo:write or flotta:manage', 403);
  const p = await c.env.DB.prepare(`SELECT id, handle FROM todo_principal WHERE agent_token_id = ?1 AND kind = 'agent' AND disabled_at IS NULL`)
    .bind(tok.id).first<{ id: string; handle: string }>();
  if (!p) throw new Problem('this token belongs to no enabled agent principal', 403);
  return p;
}

export function registerClaim(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/incidents/:id/claim', async c => {
    const p = await principalOf(c), db = c.env.DB, now = new Date();
    const inc = await db.prepare(SELECT).bind(c.req.param('id')).first<Row>();
    if (!inc) throw new Problem('incident not found', 404);
    if (!OFFERED.includes(inc.state as State)) throw new Problem(`not claimable in state ${inc.state}`, 409, 'state');
    if (inc.assigned_principal_id !== p.id) throw new Problem('this incident is assigned to another manager', 409, 'not_assignee');
    const fleet = (await getFleet(db, inc.fleet_id))!;
    if (!chain(targetOf(inc), await facts(db, fleet, now)).chain.some(m => m.principal_id === p.id)) {
      throw new Problem('you are not fit or no longer in the chain for this target', 409, 'unfit');
    }
    const claim = secret(), fence = inc.fence + 1, until = plusMin(now, ATTEMPT_MIN);
    const ok = await move(db, inc, 'atveve', now, { fence, claim_hash: await hashToken(claim), claimed_by: p.id, claimed_at: iso(now),
      attempt_until: until, nonce_hash: null, nonce_fence: null }, { kind: 'claimed', body: { by: p.handle, fence, attempt_until: until } });
    if (!ok) throw new Problem('the incident changed meanwhile; read it again', 409, 'cas');
    const target = inc.agent ? `agent:${inc.agent}` : `box:${inc.box_name}`;
    return c.json({ incident: inc.id, target, box: inc.box_name, fence, claim, attempt_until: until, state: 'atveve' });
  });

  app.post('/api/flotta/v1/incidents/:id/release', async c => {
    const p = await principalOf(c), db = c.env.DB, now = new Date();
    const inc = await db.prepare(SELECT).bind(c.req.param('id')).first<Row>();
    if (!inc) throw new Problem('incident not found', 404);
    const body = await c.req.json().catch(() => ({})) as Record<string, unknown>;
    if (!CLAIMED.includes(inc.state as State) || inc.claimed_by !== p.id) throw new Problem('you do not hold this incident', 409, 'state');
    if (body.fence !== inc.fence) throw new Problem('stale fence', 409, 'stale');
    if (inc.drain) throw new Problem('already draining', 409, 'draining');
    // a futó művelet előbb lezárul: a drain jelzi, az advance (most vagy a cron) adja át
    if (!await move(db, inc, inc.state as State, now, { drain: 'handover' }, { kind: 'released', body: { by: p.handle } })) {
      throw new Conflict('cas', 'the incident changed meanwhile');
    }
    await advance(db, (await getFleet(db, inc.fleet_id))!, now, inc.id);
    const after = await db.prepare('SELECT state FROM flotta_incident WHERE id = ?1').bind(inc.id).first<{ state: string }>();
    return c.json({ state: after!.state });
  });
}
