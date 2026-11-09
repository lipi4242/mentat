// Az elutasított box-jelentés nem lehet néma (11-08): egy elutasított jelentés NEM
// frissíti a box last_report_at-ét (a dead-man így megszólal, ha minden jelentés bukik),
// és REJECT_AFTER egymás utáni elutasítás után box-incidens nyílik (`elutasitott-jelentes`).
// Az ok zárt kód, nem a hibaszöveg: a feladat- és levélszöveg csak felsorolt értékből épül.
// Az első elfogadott jelentés nullázza a számlálót és lezárja az incidenst (ingest.ts).
import { newId } from '../todo/id';
import { event, iso, REJECTED, type Box, type RejectCode } from './types';

export const REJECT_AFTER = 3;

export async function recordRejection(db: D1Database, box: Box, code: RejectCode, at: Date): Promise<number> {
  const row = await db.prepare(`UPDATE flotta_box SET rejected_count = rejected_count + 1, last_reject = ?1 WHERE id = ?2 RETURNING rejected_count`)
    .bind(code, box.id).first<{ rejected_count: number }>();
  const n = row?.rejected_count ?? 0;
  if (n >= REJECT_AFTER) {
    const id = newId(), detail = `${n} egymás utáni elutasított jelentés; utolsó ok: ${code}`;
    const bump = await db.prepare(`UPDATE flotta_incident SET red_count = red_count + 1, last_red_at = ?1, detail = ?2
        WHERE box_id = ?3 AND subject = ?4 AND check_key = ?5 AND status = 'open'`).bind(iso(at), detail, box.id, `box:${box.name}`, REJECTED).run();
    if (!bump.meta.changes) {
      const ins = await db.prepare(`INSERT OR IGNORE INTO flotta_incident (id, fleet_id, box_id, subject, agent, check_key, detail, opened_at, last_red_at)
          VALUES (?1, ?2, ?3, ?4, NULL, ?5, ?6, ?7, ?7)`).bind(id, box.fleet_id, box.id, `box:${box.name}`, REJECTED, detail, iso(at)).run();
      if (ins.meta.changes) await event(db, id, at, 'opened', { check: REJECTED, code });
    }
  }
  return n;
}
