// Eszkaláció a tulajdonoshoz, cronból. Nincs benne LLM és nincs benne ágens:
// egyszerűbb, mint amit figyel. Mikor megy levél (flotta-menedzser):
//   - `ember-kell` (a lánc üres = fedetlen cél, a lánc elfogyott, a keret elfogyott,
//     bizonytalan hatás, biztonsági ok) → azonnal (a következő cron-körben); kivétel a
//     menedzser nélküli flotta, ott a #53-as debounce marad (2 egymás utáni piros; a dead-man azonnal)
//   - emberi átvétel után nem szólunk újra (az ember már tudja)
//   - minden más nyitott incidens → ha escalate_min-nél régebbi (alap: 60 perc)
//   - még nyitva                → repeat_min-enként újra (alap: 6 óra)
//   - megoldódott, és ment róla levél → egy rövid „megoldva”
// Idempotens: a küldés előtt feltételes UPDATE foglalja le (mail_count / resolved_mail_at);
// egy újrafutó cron nem küld kétszer. Sikertelen küldésnél a foglalás visszaáll.
import { sendNotice } from '../../lib/email';
import { adminEmails, brand, type Env } from '../../types';
import { incidentMail, type MailKind } from './mail';
import { attemptLines } from './attempts';
import { DEADMAN, event, iso, minutesBetween, OVERLOAD, type Fleet, type Incident, type Row } from './types';
import { mailsLastHour, overload } from './limits';

export type Plan = { kind: MailKind; why: string } | null;
/** Az incidensre vonatkozó tények: emberhez került-e, és van-e egyáltalán menedzser a flottában. */
export type Context = { humanNeeded: boolean; managerless: boolean; humanTook: boolean };

/** Tiszta döntés: kell-e most levél erről az incidensről. */
export function decide(inc: Incident, fleet: Fleet, ctx: Context, now: Date): Plan {
  if (inc.status === 'resolved') return inc.mail_count > 0 && !inc.resolved_mail_at ? { kind: 'resolved', why: 'megoldódott' } : null;
  if (inc.mail_count > 0) {
    return minutesBetween(inc.last_mail_at!, now) >= fleet.repeat_min ? { kind: 'repeat', why: `${fleet.repeat_min} perce szóltunk utoljára` } : null;
  }
  if (inc.check_key === OVERLOAD) return { kind: 'first', why: 'túl sok hiba egyszerre: összevonva' };
  if (ctx.humanTook) return null;
  if (ctx.humanNeeded) {
    if (!ctx.managerless) return { kind: 'first', why: `emberi beavatkozás kell: ${inc.human_reason ?? 'a lánc üres'}` };
    if (inc.check_key === DEADMAN || inc.red_count >= fleet.debounce_reports) return { kind: 'first', why: 'nincs illetékes felelős ágens' };
    return null;
  }
  if (minutesBetween(inc.opened_at, now) >= fleet.escalate_min) return { kind: 'first', why: `${fleet.escalate_min} perc alatt nem oldódott meg` };
  return null;
}

async function claim(db: D1Database, inc: Incident, kind: MailKind, now: Date) {
  const r = kind === 'resolved'
    ? await db.prepare('UPDATE flotta_incident SET resolved_mail_at = ?1 WHERE id = ?2 AND resolved_mail_at IS NULL').bind(iso(now), inc.id).run()
    : await db.prepare(`UPDATE flotta_incident SET mail_count = mail_count + 1, last_mail_at = ?1, first_mail_at = coalesce(first_mail_at, ?1)
        WHERE id = ?2 AND mail_count = ?3`).bind(iso(now), inc.id, inc.mail_count).run();
  return r.meta.changes === 1;
}

async function release(db: D1Database, inc: Incident, kind: MailKind) {
  if (kind === 'resolved') await db.prepare('UPDATE flotta_incident SET resolved_mail_at = NULL WHERE id = ?1').bind(inc.id).run();
  else await db.prepare('UPDATE flotta_incident SET mail_count = ?1, last_mail_at = ?2, first_mail_at = ?3 WHERE id = ?4 AND mail_count = ?5')
    .bind(inc.mail_count, inc.last_mail_at, inc.first_mail_at, inc.id, inc.mail_count + 1).run();
}

export async function escalate(env: Env, fleet: Fleet, now: Date, deadline?: number) {
  const db = env.DB, out = { sent: [] as string[], failed: [] as string[] };
  let budget = fleet.max_mails_per_hour - await mailsLastHour(db, fleet.id, now), throttled = false;
  const to = fleet.owner_email?.trim() || adminEmails(env)[0];
  const managerless = !(await db.prepare('SELECT 1 FROM flotta_manager WHERE fleet_id = ?1').bind(fleet.id).first());
  const { results } = await db.prepare(`SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id
      WHERE i.fleet_id = ?1 AND ((i.status = 'open' AND b.disabled_at IS NULL) OR (i.status = 'resolved' AND i.mail_count > 0 AND i.resolved_mail_at IS NULL))
      ORDER BY i.opened_at`)
    .bind(fleet.id).all<Row>();
  for (const inc of results) {
    const plan = decide(inc, fleet, { humanNeeded: inc.state === 'ember-kell', managerless, humanTook: inc.human_by !== null }, now);
    if (!plan) continue;
    if (!to) { console.error('flotta-escalation: no owner e-mail (owner_email / ADMIN_EMAILS)'); return out; }
    // óránkénti levél-keret (AD-09): a felette lévő levél vár, és egy összegző incidens jelzi
    if (inc.check_key !== OVERLOAD && budget <= 0) {
      if (!throttled) await overload(db, fleet, inc.box_id, `óránként több mint ${fleet.max_mails_per_hour} levél; a többi visszatartva`, now);
      throttled = true;
      continue;
    }
    if (deadline !== undefined && Date.now() > deadline) break;   // a flotta időkerete elfogyott
    if (!await claim(db, inc, plan.kind, now)) continue;  // egy másik futás már elvitte
    try {
      await sendNotice(env, to, incidentMail(plan.kind, inc, plan.why, brand(env), fleet.repeat_min, await attemptLines(db, inc.id).catch(() => [])));
    } catch (err) {
      await release(db, inc, plan.kind);
      console.error('flotta-escalation-failed', inc.id, err);
      out.failed.push(`${plan.kind}:${inc.id}`);
      await note(db, inc.id, now, 'mail_failed', { kind: plan.kind, error: String((err as Error).message ?? err).slice(0, 200) });
      continue;
    }
    out.sent.push(`${plan.kind}:${inc.id}`);
    if (inc.check_key !== OVERLOAD) budget--;
    // A levél kiment, a foglalás marad: a történet-sor hibája nem küldheti újra
    await note(db, inc.id, now, `mail_${plan.kind}`, { why: plan.why });
  }
  return out;
}

async function note(db: D1Database, id: string, at: Date, kind: string, body: unknown) {
  try {
    await event(db, id, at, kind, body);
  } catch (err) {
    console.error('flotta-event-failed', id, kind, err);
  }
}
