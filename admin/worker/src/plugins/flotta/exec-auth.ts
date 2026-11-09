// A végrehajtó (`fleet repair-exec`, a célboxon) hitelesítése (flotta-menedzser). Három dolog együtt:
//   1. a box jelentő tokenje → melyik box hív (v1-ben csak a saját boxán érhető el a cél);
//   2. a claim titka → a principal átvétele (hash-egyezés);
//   3. a fence → a legfrissebb generáció; átadás után a régi token egyetlen lépést sem tehet.
// Hiba: 403 (rossz box/titok) vagy 409 kóddal (stale, expired, draining, state, target).
import type { Context } from 'hono';
import type { AppEnv } from '../../types';
import { hashToken } from '../../lib/tokens';
import { boxOf } from './report-route';
import { CLAIMED, RESTART_STEPS, STEPS, type State, type Step } from './states';
import { Problem, type Box, type Row } from './types';

const SELECT = 'SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id WHERE i.id = ?1';
export const OP_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$/;

export type ExecCtx = { box: Box; inc: Row; body: Record<string, unknown> };

export async function execAuth(c: Context<AppEnv>, states: readonly State[] = CLAIMED, allowDrain = false): Promise<ExecCtx> {
  const box = await boxOf(c);
  const body = await c.req.json().catch(() => null) as Record<string, unknown> | null;
  if (!body || typeof body !== 'object') throw new Problem('body must be an object', 400);
  const inc = await c.env.DB.prepare(SELECT).bind(c.req.param('id')).first<Row>();
  if (!inc || inc.fleet_id !== box.fleet_id) throw new Problem('incident not found', 404);
  if (inc.box_id !== box.id) throw new Problem('this box cannot reach the target (v1: own box only)', 403, 'reach');
  // előbb a fence: átadás/lezárás után a régi generáció 409 stale-t kap, nem 403-at
  if (body.fence !== inc.fence || !inc.claim_hash) throw new Problem('stale fence (handed over, closed or not claimed)', 409, 'stale');
  if (typeof body.claim !== 'string' || await hashToken(body.claim) !== inc.claim_hash) throw new Problem('claim does not match', 403, 'claim');
  if (!states.includes(inc.state as State)) throw new Problem(`not allowed in state ${inc.state}`, 409, 'state');
  if (inc.drain && !allowDrain) throw new Problem('handover or human takeover pending: no new work', 409, 'draining');
  return { box, inc, body };
}

export function assertWindow(inc: Row, now: Date) {
  if (!inc.attempt_until || Date.parse(inc.attempt_until) <= now.getTime()) throw new Problem('attempt window expired', 409, 'expired');
}

/**
 * Desktop-cél (saját gép, nincs always-on processz/unit/híd): újraindító lépés nem értelmezhető. Két
 * forrás, a szigorúbb nyer: a box fajtája (`flotta_box.kind`) VAGY az ágens saját jelentése
 * (`desktop: true`, a registry `supervision: none`-ja). Így a kettő eltérése sem enged újraindítást.
 */
export async function isDesktopTarget(db: D1Database, box: Box, inc: Row): Promise<boolean> {
  if (box.kind === 'desktop') return true;
  if (!inc.agent) return false;
  const a = await db.prepare('SELECT result_json FROM flotta_agent WHERE fleet_id = ?1 AND name = ?2').bind(inc.fleet_id, inc.agent).first<{ result_json: string }>();
  try { return !!a && JSON.parse(a.result_json).desktop === true; } catch { return false; }
}

export async function assertStepFits(db: D1Database, box: Box, inc: Row, step: Step) {
  if (RESTART_STEPS.includes(step) && await isDesktopTarget(db, box, inc)) {
    throw new Problem(`${step} is meaningless on a desktop target (no always-on process/unit/bridge): only doctor and postcheck`, 409, 'desktop');
  }
}

export function parseStep(body: Record<string, unknown>, inc: Row): { step: Step; target: string } {
  const step = body.step as Step;
  if (!STEPS.includes(step)) throw new Problem(`step must be one of ${STEPS.join(', ')}`, 400);
  const target = inc.agent ? `agent:${inc.agent}` : `box:${inc.box_name}`;
  if (body.target !== target) throw new Problem(`target must be ${target}`, 409, 'target');
  if (!inc.agent && step !== 'doctor' && step !== 'postcheck') throw new Problem('a box incident allows only doctor / postcheck', 409, 'target');
  return { step, target };
}
