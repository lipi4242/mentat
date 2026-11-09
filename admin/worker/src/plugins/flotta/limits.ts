// Korlátok (CISO AD-09): egy elszabadult vagy rosszindulatú box se árassza el a flottát.
// Flottánként: nyitott incidensek száma, óránként létrehozott feladatok, óránként küldött
// levelek. A korlát felett a további tétel nem vész el és nem sokszorozódik: EGY összegző
// incidens (`fleet:<id>` / tulterheles) nyílik, arról EGY levél megy, a visszatartott
// feladatok és levelek pedig akkor mennek, amikor a keret felszabadul.
import { newId } from '../todo/id';
import { event, iso, OVERLOAD, type Fleet } from './types';

const HOUR = 3600000;
const since = (at: Date) => iso(new Date(at.getTime() - HOUR));

/** Nyitott incidensek a flottában (vagy egy boxon), az összegző nélkül. */
export const openCount = async (db: D1Database, fleetId: string, boxId?: string) => (await db.prepare(
  `SELECT count(*) AS n FROM flotta_incident WHERE fleet_id = ?1 AND status = 'open' AND check_key <> ?2 AND (?3 IS NULL OR box_id = ?3)`)
  .bind(fleetId, OVERLOAD, boxId ?? null).first<{ n: number }>())!.n;

async function eventsLastHour(db: D1Database, fleetId: string, kinds: string, at: Date) {
  return (await db.prepare(`SELECT count(*) AS n FROM flotta_incident_event e JOIN flotta_incident i ON i.id = e.incident_id
      WHERE i.fleet_id = ?1 AND e.kind IN (${kinds}) AND e.at >= ?2 AND i.check_key <> ?3`)
    .bind(fleetId, since(at), OVERLOAD).first<{ n: number }>())!.n;
}
export const tasksLastHour = (db: D1Database, fleetId: string, at: Date) => eventsLastHour(db, fleetId, `'task'`, at);
export const mailsLastHour = (db: D1Database, fleetId: string, at: Date) =>
  eventsLastHour(db, fleetId, `'mail_first','mail_repeat','mail_resolved'`, at);

/** Megnyitja vagy frissíti a flotta összegző incidensét (egy nyitott lehet belőle). */
export async function overload(db: D1Database, fleet: Fleet, boxId: string, reason: string, at: Date) {
  const subject = `fleet:${fleet.id}`, now = iso(at);
  const bump = await db.prepare(`UPDATE flotta_incident SET red_count = red_count + 1, last_red_at = ?1, detail = ?2
      WHERE fleet_id = ?3 AND subject = ?4 AND check_key = ?5 AND status = 'open'`).bind(now, reason, fleet.id, subject, OVERLOAD).run();
  if (bump.meta.changes) return;
  const id = newId();
  const ins = await db.prepare(`INSERT OR IGNORE INTO flotta_incident (id, fleet_id, box_id, subject, agent, check_key, detail, opened_at, last_red_at)
      VALUES (?1, ?2, ?3, ?4, NULL, ?5, ?6, ?7, ?7)`).bind(id, fleet.id, boxId, subject, OVERLOAD, reason, now).run();
  if (ins.meta.changes) await event(db, id, at, 'opened', { check: OVERLOAD, reason });
}

/** Ha minden keret alatt van, az összegző incidens lezárul (a „megoldva” levél a szokásos úton megy). */
export async function settle(db: D1Database, fleet: Fleet, at: Date) {
  if (await openCount(db, fleet.id) >= fleet.max_open_incidents) return;
  if (await tasksLastHour(db, fleet.id, at) >= fleet.max_tasks_per_hour) return;
  if (await mailsLastHour(db, fleet.id, at) >= fleet.max_mails_per_hour) return;
  const r = await db.prepare(`UPDATE flotta_incident SET status = 'resolved', resolved_at = ?1, resolve_note = 'a korlátok alá került'
      WHERE fleet_id = ?2 AND subject = ?3 AND check_key = ?4 AND status = 'open' RETURNING id`)
    .bind(iso(at), fleet.id, `fleet:${fleet.id}`, OVERLOAD).first<{ id: string }>();
  if (r) await event(db, r.id, at, 'resolved', { note: 'a korlátok alá került' });
}
