// A flotta-ellenőrzés cron-köre (wrangler.toml [triggers], 5 percenként):
//   1. dead-man: a deadman_min óta nem jelentő box → box-incidens (a soha nem
//      jelentőnél a regisztráció ideje számít: a félbehagyott bekötés is látszik)
//   2. az állapotgép időzítői: kiosztás, 10 perces claim, 30 perces keret, átadás (assign.ts)
//   3. a menedzserek feladatai — az állapot vetülete (nyitás / zárás)
//   4. eszkaláció e-mailben
//   5. a 7 napnál régebbi nyers jelentések törlése
// Egy flotta vagy egy fázis hibája nem állítja meg a többit: az e-mail akkor is megy,
// ha a feladat-tükör bukik.
import type { Env } from '../../types';
import { newId } from '../todo/id';
import { advance } from './assign';
import { escalate } from './escalate';
import { settle } from './limits';
import { syncTasks } from './todo-mirror';
import { DEADMAN, event, iso, minutesBetween, type Box, type Fleet } from './types';

const KEEP_REPORTS_DAYS = 7;

export async function deadman(db: D1Database, fleet: Fleet, now: Date) {
  // a desktop (saját gép, csak futó session jelent) csendje nem hiba: nincs dead-man
  const { results } = await db.prepare(`SELECT * FROM flotta_box WHERE fleet_id = ?1 AND disabled_at IS NULL AND kind = 'box'`).bind(fleet.id).all<Box>();
  const cutoff = iso(new Date(now.getTime() - fleet.deadman_min * 60000));
  const opened: string[] = [];
  for (const box of results) {
    const since = box.last_report_at ?? box.created_at;
    if (since > cutoff) continue;
    const detail = box.last_report_at ? `utolsó jelentés: ${box.last_report_at} (${Math.floor(minutesBetween(since, now))} perce)`
      : `még soha nem jelentett (regisztrálva: ${box.created_at})`;
    // A feltétel az SQL-ben is áll: ha a box a pillanatkép óta jelentett, nem nyílik incidens.
    // A nyitott dead-man incidenst nem „pirosítjuk” újra (INSERT OR IGNORE): a red_count a jelentéseké.
    const id = newId();
    const ins = await db.prepare(`INSERT OR IGNORE INTO flotta_incident
        (id, fleet_id, box_id, subject, agent, check_key, detail, opened_at, last_red_at)
        SELECT ?1, ?2, ?3, ?4, NULL, ?5, ?6, ?7, ?7 WHERE EXISTS (SELECT 1 FROM flotta_box WHERE id = ?3 AND disabled_at IS NULL
          AND coalesce(last_report_at, created_at) <= ?8)`)
      .bind(id, fleet.id, box.id, `box:${box.name}`, DEADMAN, detail, iso(now), cutoff).run();
    if (ins.meta.changes === 1) {
      await event(db, id, now, 'opened', { check: DEADMAN, detail });
      opened.push(id);
    }
  }
  return opened;
}

async function phase<T>(name: string, fleetId: string, fn: () => Promise<T>): Promise<T | { error: string }> {
  try {
    return await fn();
  } catch (err) {
    console.error(`flotta-cron-${name}-failed`, fleetId, err);
    return { error: String(err) };
  }
}

/** Flottánkénti időkeret: egy lassú vagy elszabadult flotta nem viszi el a kört a többiek elől. */
export const FLEET_BUDGET_MS = 20000;

export async function runCron(env: Env, now: Date, budgetMs = FLEET_BUDGET_MS) {
  const { results: fleets } = await env.DB.prepare('SELECT * FROM flotta_fleet ORDER BY id').all<Fleet>();
  const out: Record<string, unknown> = {};
  for (const fleet of fleets) {
    const deadline = Date.now() + budgetMs;
    const left = () => Date.now() <= deadline;
    const dead = await phase('deadman', fleet.id, () => deadman(env.DB, fleet, now));
    const moved = left() ? await phase('advance', fleet.id, () => advance(env.DB, fleet, now)) : { error: 'time budget' };
    const tasks = left() ? await phase('tasks', fleet.id, () => syncTasks(env.DB, fleet, now)) : { error: 'time budget' };
    // az e-mail mindig fut, saját (fél) kerettel: a feladat-tükör ideje sem veheti el
    const mail = await phase('escalate', fleet.id, () => escalate(env, fleet, now, Date.now() + budgetMs / 2));
    await phase('settle', fleet.id, () => settle(env.DB, fleet, now));
    out[fleet.id] = { deadman: dead, moved, tasks: tasks ?? null, mail };
  }
  const cutoff = iso(new Date(now.getTime() - KEEP_REPORTS_DAYS * 86400000));
  await phase('prune', '*', () => env.DB.prepare('DELETE FROM flotta_report WHERE received_at < ?1').bind(cutoff).run());
  return out;
}
