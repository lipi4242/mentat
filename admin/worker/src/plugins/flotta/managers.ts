// A menedzser-lánc egy célra (flotta-menedzser). Determinisztikus: elsőbbség agent > box > *,
// azon belül rang, döntetlennél a principal handle-je. Egy principal csak egyszer, a legjobb
// helyén. Kimarad maga a cél-ágens (önmagát nem javítja), aki nem ÉRI EL a célt (v1: csak a saját boxát), és aki javításra
// ALKALMATLAN: dead-man szerint néma (a boxa vagy ő maga), a boxa javító-próbája piros vagy
// nem mért, vagy az ágensén javítást érintő ellenőrzés (REPAIR_CHECKS) piros. Egy apró, nem
// javítást érintő hiba (pl. Telegram-küldés) nem zár ki. A lánc tiszta függvény; a tényeket
// a `facts` gyűjti egyszer, körönként.
import { REPAIR_CHECKS } from './states';
import { DEADMAN, minutesBetween, type Box, type Fleet, type Manager } from './types';

export type Member = Manager & { handle: string };
export type Target = { agent: string | null; box: string };
export type Facts = {
  managers: Member[]; fleet: Fleet; now: Date;
  agentBox: Map<string, { box: string; last_seen_at: string }>;
  boxes: Map<string, Box>;
  red: Map<string, Set<string>>;          // 'agent:x' | 'box:x' → nyitott incidensek ellenőrzés-kulcsai
};

export async function facts(db: D1Database, fleet: Fleet, now: Date): Promise<Facts> {
  const managers = (await db.prepare(`SELECT m.*, p.handle FROM flotta_manager m
      JOIN todo_principal p ON p.id = m.principal_id AND p.disabled_at IS NULL
      WHERE m.fleet_id = ?1`).bind(fleet.id).all<Member>().catch(err => {
      // todo nélküli példányon (nincs todo_principal) ez várt: nincs menedzser → e-mail-út
      console.error('flotta-roster-failed', fleet.id, err);
      return { results: [] as Member[] };
    })).results;
  const agentBox = new Map<string, { box: string; last_seen_at: string }>();
  for (const a of (await db.prepare(`SELECT a.name, a.last_seen_at, b.name AS box FROM flotta_agent a JOIN flotta_box b ON b.id = a.box_id WHERE a.fleet_id = ?1`)
    .bind(fleet.id).all<{ name: string; box: string; last_seen_at: string }>()).results) agentBox.set(a.name, a);
  const boxes = new Map((await db.prepare('SELECT * FROM flotta_box WHERE fleet_id = ?1').bind(fleet.id).all<Box>()).results.map(b => [b.name, b]));
  const red = new Map<string, Set<string>>();
  for (const r of (await db.prepare(`SELECT subject, check_key FROM flotta_incident WHERE fleet_id = ?1 AND status = 'open'`)
    .bind(fleet.id).all<{ subject: string; check_key: string }>()).results) {
    if (!red.has(r.subject)) red.set(r.subject, new Set());
    red.get(r.subject)!.add(r.check_key);
  }
  return { managers, fleet, now, agentBox, boxes, red };
}

/** Desktop-menedzser alkalmassága: a sessionje ennyi percen belül jelentett (a session induláskor és
 *  a tickjeiben hívja a `fleet flotta-report`-ot; a 10 perces claim-időn belül legyen friss). */
export const DESKTOP_FRESH_MIN = 15;

const PRECEDENCE = (scope: string) => scope.startsWith('agent:') ? 0 : scope.startsWith('box:') ? 1 : 2;

export const covers = (scope: string, t: Target) =>
  scope === '*' || scope === `box:${t.box}` || (t.agent !== null && scope === `agent:${t.agent}`);

/** null = alkalmas; különben az ok (a coverage-jelentésbe is ez kerül). */
export function unfit(m: Member, f: Facts): string | null {
  const seen = f.agentBox.get(m.agent);
  if (!seen) return 'nem mért (az ágense még nem szerepelt jelentésben)';
  const box = f.boxes.get(seen.box);
  if (!box || box.disabled_at) return `a boxa (${seen.box}) nincs a flottában`;
  if (f.red.get(`box:${box.name}`)?.has(DEADMAN)) return `néma: a ${box.name} box nem jelent (dead-man)`;
  // a desktopon nincs dead-man: ott a futó session a jel, rövid ablakkal (DESKTOP_FRESH_MIN)
  const window = box.kind === 'desktop' ? DESKTOP_FRESH_MIN : f.fleet.deadman_min;
  const quiet = (t: string | null) => t === null || minutesBetween(t, f.now) >= window;
  if (quiet(box.last_report_at) || quiet(seen.last_seen_at)) {
    return box.kind === 'desktop' ? `a sessionje ${window} perce nem jelentett (desktop)` : `néma: ${window} perce nincs friss jelentés róla`;
  }
  if (box.repair_ok === null) return `a ${box.name} box javító-próbája nem mért`;
  if (box.repair_ok === 0) return `a ${box.name} box javító-próbája piros`;
  const bad = REPAIR_CHECKS.filter(k => f.red.get(`agent:${m.agent}`)?.has(k));
  return bad.length ? `javító-képessége piros (${bad.join(', ')})` : null;
}

/** v1: csak a saját box érhető el. A box-közi elérés (kényszer-parancsos ssh) későbbi lépés. */
export const reaches = (m: Member, t: Target, f: Facts) => f.agentBox.get(m.agent)?.box === t.box;

export type Chain = { chain: Member[]; excluded: Array<{ handle: string; agent: string; why: string }> };

export function chain(t: Target, f: Facts): Chain {
  const sorted = f.managers.filter(m => covers(m.scope, t)).sort((a, b) =>
    PRECEDENCE(a.scope) - PRECEDENCE(b.scope) || a.rank - b.rank || (a.handle < b.handle ? -1 : a.handle > b.handle ? 1 : 0));
  const seen = new Set<string>(), out: Chain = { chain: [], excluded: [] };
  for (const m of sorted) {
    if (seen.has(m.principal_id)) continue;   // egy principal egyszer, a legjobb helyén
    seen.add(m.principal_id);
    // önmagát nem javítja: a saját újraindítása a végrehajtót is megölné (bizonytalan kimenet)
    const why = t.agent === m.agent ? 'ő maga a cél' : !reaches(m, t, f) ? `nem éri el a ${t.box} boxot (v1: csak a saját boxát)` : unfit(m, f);
    if (why) out.excluded.push({ handle: m.handle, agent: m.agent, why });
    else out.chain.push(m);
  }
  return out;
}

export const targetOf = (inc: { agent: string | null; box_name: string }): Target => ({ agent: inc.agent, box: inc.box_name });
