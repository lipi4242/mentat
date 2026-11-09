// Incidens-életút: (alany, ellenőrzés) páronként EGY nyitott incidens. A piros
// jelentés ugyanazt a sort frissíti (red_count, last_red_at); a zöld lezárja.
// A dedupe-ot a részleges UNIQUE index tartja (flotta_incident_open), nem a kód:
// két egyidejű jelentésből sem lesz két nyitott incidens. Minden lekérdezés a box_id-re
// szűkít: egy box tokenje csak a saját boxa incidenseit nyithatja, frissítheti, zárhatja.
import { newId } from '../todo/id';
import { event, iso, type Fleet, type Incident } from './types';
import { openCount, overload } from './limits';
import { CLAIMED, move, type State } from './states';

export type Subject = { fleet_id: string; box_id: string; subject: string; agent: string | null };

/** Piros jelentés egy (alany, ellenőrzés) párra. A flotta korlátja felett ÚJ incidens nem nyílik:
 *  az összegző incidens kap egy pirosat (limits.ts), és `incident: null` a válasz. */
export async function redFor(db: D1Database, s: Subject, check: string, detail: string, at: Date,
  fleet: Fleet): Promise<{ incident: Incident | null; opened: boolean }> {
  const bump = await db.prepare(`UPDATE flotta_incident SET red_count = red_count + 1, last_red_at = ?1, detail = ?2
      WHERE box_id = ?3 AND fleet_id = ?4 AND subject = ?5 AND check_key = ?6 AND status = 'open'`)
    .bind(iso(at), detail, s.box_id, s.fleet_id, s.subject, check).run();
  let opened = false;
  if (!bump.meta.changes && await openCount(db, s.fleet_id) >= fleet.max_open_incidents) {
    await overload(db, fleet, s.box_id, `több mint ${fleet.max_open_incidents} nyitott incidens; a további hibák összevonva`, at);
    return { incident: null, opened: false };
  }
  // boxonkénti rész a keretből: egy box se fogyassza el a többiek elől
  if (!bump.meta.changes && await openCount(db, s.fleet_id, s.box_id) >= fleet.max_open_per_box) {
    await overload(db, fleet, s.box_id, `egy box több mint ${fleet.max_open_per_box} nyitott incidense; a további hibái összevonva`, at);
    return { incident: null, opened: false };
  }
  if (!bump.meta.changes) {
    const id = newId();
    const ins = await db.prepare(`INSERT OR IGNORE INTO flotta_incident
        (id, fleet_id, box_id, subject, agent, check_key, detail, opened_at, last_red_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?8)`)
      .bind(id, s.fleet_id, s.box_id, s.subject, s.agent, check, detail, iso(at)).run();
    opened = ins.meta.changes === 1;
    if (opened) await event(db, id, at, 'opened', { check, detail });
  }
  const incident = await db.prepare(`SELECT * FROM flotta_incident WHERE box_id = ?1 AND fleet_id = ?2 AND subject = ?3 AND check_key = ?4 AND status = 'open'`)
    .bind(s.box_id, s.fleet_id, s.subject, check).first<Incident>();
  // a részleges UNIQUE index egy MÁSIK box nyitott incidense miatt is elnyelheti a beszúrást:
  // ilyenkor ez a box nem ír bele (az ágens-kötés ezt már a bejáratnál kizárja)
  if (!incident) throw new Error(`flotta: open incident for ${s.subject}/${check} belongs to another box`);
  return { incident, opened };
}

/**
 * Lezárja a box nyitott incidenseit, amelyekre `close` igaz — de csak azokat, amelyeken senki
 * nem tart fence-t (nyitott, kiosztva, átadva, ember-kell). Az átvett incidens (átvéve / javít /
 * ellenőrzés) csak az ellenőrző nonce-szal zárul (flotta-menedzser); egy kivezetett boxé a lejárt
 * keret után emberhez kerül, és a kivezetett box incidense nem megy e-mailbe.
 */
export async function resolveWhere(db: D1Database, boxId: string, close: (inc: Incident) => boolean, note: string, at: Date) {
  const { results } = await db.prepare(`SELECT * FROM flotta_incident WHERE box_id = ?1 AND status = 'open'`).bind(boxId).all<Incident>();
  const closed: Incident[] = [];
  for (const inc of results) {
    if (!close(inc) || CLAIMED.includes(inc.state as State)) continue;
    if (await move(db, inc, 'megoldva', at, { resolve_note: note }, { kind: 'resolved', body: { note } })) closed.push(inc);
  }
  return closed;
}

/** Lezárja az alany nyitott incidenseit ezen a boxon, kivéve a még piros ellenőrzéseket. */
export const resolveExcept = (db: D1Database, boxId: string, subject: string, stillRed: string[], note: string, at: Date) =>
  resolveWhere(db, boxId, inc => inc.subject === subject && !stillRed.includes(inc.check_key), note, at);
