// Egy box jelentésének feldolgozása: box- és ágens-állapot, nyers jelentés,
// incidensek nyitása (dedupe) és lezárása. Csak D1, nincs hálózat: a box kérését
// semmi lassú nem tartja fel; e-mail csak a cronból megy.
import { newId } from '../todo/id';
import { redFor, resolveExcept, resolveWhere } from './incidents';
import { iso, Problem, type Box, type Fleet } from './types';
import type { Report } from './validate';

export type IngestResult = { opened: string[]; resolved: string[]; open: number };

export async function ingest(db: D1Database, box: Box, fleet: Fleet, report: Report, at: Date): Promise<IngestResult> {
  const now = iso(at), out: IngestResult = { opened: [], resolved: [], open: 0 };
  // Egy ágens egy boxhoz tartozik. Más box ágensét jelenteni (zárni vagy pirosítani) tilos;
  // az áthelyezés kifejezett admin-lépés (POST /agents/:name/release). Írás előtt nézzük.
  const names = report.agents.map(a => a.agent);
  if (names.length) {
    const { results: foreign } = await db.prepare(`SELECT name FROM flotta_agent WHERE fleet_id = ?1 AND box_id <> ?2
        AND name IN (${names.map((_, i) => `?${i + 3}`).join(',')})`).bind(box.fleet_id, box.id, ...names).all<{ name: string }>();
    if (foreign.length) throw new Problem(`agent(s) registered on another box: ${foreign.map(f => f.name).join(', ')} — move them in the admin first`, 409, 'cross-box');
  }
  await db.batch([
    // csak az elfogadott jelentés frissíti a last_report_at-et (a dead-man ezt nézi), és nullázza az elutasítás-számlálót
    db.prepare(`UPDATE flotta_box SET last_report_at = ?1, fleet_version = ?2, release_json = ?3, rejected_count = 0, last_reject = NULL,
        repair_ok = ?4, repair_detail = ?5 WHERE id = ?6`)
      .bind(now, report.fleet_version, report.release ? JSON.stringify(report.release) : null,
        report.repair ? (report.repair.ok ? 1 : 0) : null, report.repair?.detail ?? null, box.id),
    db.prepare('INSERT INTO flotta_report (box_id, received_at, body_json) VALUES (?1, ?2, ?3)')
      .bind(box.id, now, JSON.stringify(report)),
  ]);
  // a box jelent: a dead-man incidense (ha volt) megoldódott
  const back = await resolveExcept(db, box.id, `box:${box.name}`, [], `a box újra jelent (${now})`, at);
  out.resolved.push(...back.map(i => i.id));
  for (const a of report.agents) {
    const result = JSON.stringify({ red: a.red, unknown: a.unknown, ok: a.ok, tick: a.tick, desktop: a.desktop });
    await db.prepare(`INSERT INTO flotta_agent (id, fleet_id, name, box_id, last_seen_at, measured_at, result_json)
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        ON CONFLICT (fleet_id, name) DO UPDATE SET last_seen_at = excluded.last_seen_at,
          measured_at = excluded.measured_at, result_json = excluded.result_json WHERE flotta_agent.box_id = excluded.box_id`)
      .bind(newId(), box.fleet_id, a.agent, box.id, now, a.measured_at, result).run();
    const subject = { fleet_id: box.fleet_id, box_id: box.id, subject: `agent:${a.agent}`, agent: a.agent };
    const red = new Map<string, string>();
    for (const r of a.red) red.set(r.check, red.has(r.check) ? `${red.get(r.check)}; ${r.detail}` : r.detail);
    for (const [check, detail] of red) {
      const { incident, opened } = await redFor(db, subject, check, detail.slice(0, 1000), at, fleet);
      if (opened && incident) out.opened.push(incident.id);
    }
    const closed = await resolveExcept(db, box.id, subject.subject, [...red.keys()], `zöld jelentés a ${box.name} boxról (${now})`, at);
    out.resolved.push(...closed.map(i => i.id));
  }
  // a jelentésből kikerült ágens (dormant, kivezetett): a nyitott incidensei lezárulnak
  const gone = await resolveWhere(db, box.id, inc => inc.agent !== null && !names.includes(inc.agent),
    `kikerült a jelentésből (${box.name}, ${now})`, at);
  out.resolved.push(...gone.map(i => i.id));
  out.open = (await db.prepare(`SELECT count(*) AS n FROM flotta_incident WHERE fleet_id = ?1 AND status = 'open'`)
    .bind(box.fleet_id).first<{ n: number }>())!.n;
  return out;
}
