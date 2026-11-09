// Kiosztás, átadás, időzítők (flotta-menedzser). A cron lépteti (és a jelentés/eredmény után azonnal
// is lefut), nem a jelentések érkezése. Minden átmenet a states.ts CAS-án megy: ha valaki
// közben léptetett, ez a kör kimarad, a következő újraolvassa.
//   nyitott            → kiosztva a lánc első, még nem próbált tagjának; üres lánc → ember-kell
//   kiosztva / átadva  → 10 perc claim nélkül, vagy a kiosztott alkalmatlan lett → átadás
//   átvéve/javít/ellenőrzés → lejárt keret vagy alkalmatlan menedzser → átadás (futó művelet után)
//   box-incidens alatt az ágens-incidensek a box-incidensre várnak (nyitott, nincs kiosztás)
import { chain, facts, targetOf, type Facts } from './managers';
import { CLAIM_WAIT_MIN, CLAIMED, move, OFFERED, tried, type State } from './states';
import { DEADMAN, iso, minutesBetween, OVERLOAD, type Fleet, type Row } from './types';

const SELECT = 'SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id';

/** Fut-e még művelet (szándék rögzítve, a lépés időkorlátján belül). */
export async function runningOp(db: D1Database, incId: string, now: Date) {
  return !!await db.prepare(`SELECT 1 FROM flotta_repair_op WHERE incident_id = ?1 AND state = 'intent' AND deadline > ?2`)
    .bind(incId, iso(now)).first();
}

/** A lejárt, lezáratlan szándék „bizonytalan”: a következő lépés előtt csak-olvasó felmérés kell. */
export async function expireIntents(db: D1Database, incId: string, now: Date, all = false) {
  await db.prepare(`UPDATE flotta_repair_op SET state = 'uncertain', finished_at = ?2, summary = coalesce(summary, 'nem zárult le (bizonytalan kimenet)')
      WHERE incident_id = ?1 AND state = 'intent' AND (?3 = 1 OR deadline <= ?2)`).bind(incId, iso(now), all ? 1 : 0).run();
}

const boxWaiting = (inc: Row, f: Facts) => inc.agent !== null && !!f.red.get(`box:${inc.box_name}`)?.has(DEADMAN);

/** Átadás a lánc következő, még nem próbált tagjának — új fence, a régi token ettől nem lép. */
export async function handover(db: D1Database, inc: Row, f: Facts, now: Date, why: string) {
  const done = tried(inc);
  const next = chain(targetOf(inc), f).chain.find(m => !done.includes(m.principal_id));
  const base = { fence: inc.fence + 1, claim_hash: null, nonce_hash: null, nonce_fence: null, drain: null,
    claimed_by: null, claimed_at: null, attempt_until: null, handovers: inc.handovers + 1 };
  if (!next) return move(db, inc, 'ember-kell', now, { ...base, assigned_principal_id: null, human_reason: `a lánc elfogyott (${why})` }, { kind: 'handover', body: { why, to: null } });
  return move(db, inc, 'atadva', now, { ...base, assigned_principal_id: next.principal_id, assigned_at: iso(now),
    tried_json: JSON.stringify([...done, next.principal_id]) }, { kind: 'handover', body: { why, to: next.handle, rank: next.rank, scope: next.scope } });
}

async function assignFirst(db: D1Database, inc: Row, f: Facts, now: Date) {
  const c = chain(targetOf(inc), f), done = tried(inc);
  const next = c.chain.find(m => !done.includes(m.principal_id));
  if (!next) {
    const why = c.chain.length ? 'a lánc elfogyott' : `fedetlen cél — ${c.excluded.map(e => `${e.handle}: ${e.why}`).join('; ') || 'nincs menedzser'}`;
    return move(db, inc, 'ember-kell', now, { human_reason: why.slice(0, 500) }, { kind: 'uncovered', body: { excluded: c.excluded } });
  }
  return move(db, inc, 'kiosztva', now, { assigned_principal_id: next.principal_id, assigned_at: iso(now),
    tried_json: JSON.stringify([...done, next.principal_id]) }, { kind: 'assigned', body: { to: next.handle, rank: next.rank, scope: next.scope } });
}

/** Egy incidens egy lépése. Visszaad: történt-e átmenet. */
export async function step(db: D1Database, inc: Row, f: Facts, now: Date): Promise<boolean> {
  const state = inc.state as State;
  if (inc.drain) {
    if (await runningOp(db, inc.id, now)) return false;      // a futó művelet előbb lezárul (vagy lejár)
    await expireIntents(db, inc.id, now);
    if (inc.drain === 'human') return move(db, inc, 'ember-kell', now, { fence: inc.fence + 1, claim_hash: null, nonce_hash: null,
      nonce_fence: null, drain: null, claimed_by: null, attempt_until: null }, { kind: 'human_claim' });
    return handover(db, inc, f, now, 'átadás a futó művelet lezárulta után');
  }
  if (state === 'nyitott') return boxWaiting(inc, f) ? false : assignFirst(db, inc, f, now);
  const assignee = inc.assigned_principal_id;
  const fit = (p: string | null) => p !== null && chain(targetOf(inc), f).chain.some(m => m.principal_id === p);
  if (OFFERED.includes(state)) {
    if (boxWaiting(inc, f)) {   // a box-incidens alatt vár; a kiosztott nem számít próbáltnak
      return move(db, inc, 'nyitott', now, { assigned_principal_id: null, assigned_at: null,
        tried_json: JSON.stringify(tried(inc).filter(p => p !== assignee)) }, { kind: 'waiting', body: { on: `box:${inc.box_name}` } });
    }
    if (!fit(assignee)) return handover(db, inc, f, now, 'a kiosztott menedzser alkalmatlan lett');
    if (minutesBetween(inc.assigned_at!, now) >= CLAIM_WAIT_MIN) return handover(db, inc, f, now, `${CLAIM_WAIT_MIN} percen belül nem vette át`);
    return false;
  }
  if (CLAIMED.includes(state)) {
    const expired = inc.attempt_until !== null && Date.parse(inc.attempt_until) <= now.getTime();
    const why = expired ? 'a kísérleti keret lejárt megoldás nélkül' : !fit(inc.claimed_by) ? 'a menedzser alkalmatlan lett' : null;
    if (!why) return false;
    if (await runningOp(db, inc.id, now)) {   // átadás előtt a futó művelet lezárul; addig új nem indul
      return move(db, inc, state, now, { drain: 'handover' }, { kind: 'draining', body: { why } });
    }
    await expireIntents(db, inc.id, now);
    return handover(db, inc, f, now, why);
  }
  return false;
}

/** A flotta minden nem lezárt incidense; a box-incidensek előbb (az ágensek rájuk várnak). */
export async function advance(db: D1Database, fleet: Fleet, now: Date, only?: string) {
  const f = await facts(db, fleet, now);
  // az összegző (túlterhelés) incidens nem javítási cél: azt a levél-út viszi (limits.ts)
  const { results } = await db.prepare(`${SELECT} WHERE i.fleet_id = ?1 AND i.status = 'open' AND i.state NOT IN ('megoldva', 'ember-kell')
      AND i.check_key <> ?3 AND (?2 IS NULL OR i.id = ?2) ORDER BY i.agent IS NOT NULL, i.opened_at`).bind(fleet.id, only ?? null, OVERLOAD).all<Row>();
  let moved = 0;
  for (const inc of results) if (await step(db, inc, f, now)) moved++;
  return moved;
}

