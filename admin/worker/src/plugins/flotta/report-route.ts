// POST /api/flotta/v1/report — a box jelentése. Csak `flotta:report` tokennel, ami
// egy boxhoz van kötve, és csak a SAJÁT boxa nevében: egy másik box nevével 403.
import type { Context, Hono } from 'hono';
import type { AppEnv } from '../../types';
import { hasScope, resolveAgentToken } from '../../lib/guards';
import { ingest } from './ingest';
import { syncTasks } from './todo-mirror';
import { advance } from './assign';
import { coverage } from './coverage';
import { getFleet, isRejectCode, Problem, REPORT_SCOPE, type Box } from './types';
import { parseReport } from './validate';
import { recordRejection } from './rejection';

const MAX_BODY = 256 * 1024;
export const MIN_INTERVAL_S = 60;

export async function boxOf(c: Context<AppEnv>): Promise<Box> {
  const token = await resolveAgentToken(c.env.DB, c.req.header('X-Mentat-Token') ?? '');
  if (!token) throw new Problem('unauthorized', 401);
  if (!hasScope(token.scopes, REPORT_SCOPE)) throw new Problem(`forbidden: needs ${REPORT_SCOPE}`, 403);
  const box = await c.env.DB.prepare('SELECT * FROM flotta_box WHERE token_id = ?1 AND disabled_at IS NULL').bind(token.id).first<Box>();
  if (!box) throw new Problem('this token is not bound to an active box', 403);
  return box;
}

export function registerReport(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/report', async c => {
    const box = await boxOf(c);
    const at = new Date();
    // Ritmus-korlát boxonként (AD-09): legfeljebb egy KÍSÉRLET MIN_INTERVAL_S-enként, a tartalom
    // vizsgálata előtt (érvénytelen törzzsel sem kerülhető meg). A last_attempt_at-et írja, NEM a
    // last_report_at-et: azt csak az elfogadott jelentés frissíti (11-08, a dead-man ezt nézi).
    const claim = await c.env.DB.prepare(`UPDATE flotta_box SET last_attempt_at = ?1 WHERE id = ?2
        AND (last_attempt_at IS NULL OR last_attempt_at <= ?3)`).bind(at.toISOString(), box.id, new Date(at.getTime() - MIN_INTERVAL_S * 1000).toISOString()).run();
    if (!claim.meta.changes) throw new Problem(`too many reports: at most one per ${MIN_INTERVAL_S} s per box`, 429);
    const fleet = await getFleet(c.env.DB, box.fleet_id);
    if (!fleet) throw new Problem('unknown fleet', 404);
    let result;
    try {
      const raw = await c.req.text();
      if (raw.length > MAX_BODY) throw new Problem('report too large', 400, 'too-large');
      let body: unknown;
      try { body = JSON.parse(raw); } catch { throw new Problem('body must be valid JSON', 400, 'invalid'); }
      const report = parseReport(body);
      if (report.box !== box.name) throw new Problem(`this token reports for box ${box.name}, not ${report.box}`, 403, 'box-mismatch');
      result = await ingest(c.env.DB, box, fleet, report, at);
    } catch (err) {
      if (!(err instanceof Problem) || !isRejectCode(err.code)) throw err;
      // az elutasítás maga is jel: a box válasza és (REJECT_AFTER után) egy box-incidens mutatja
      const consecutive = await recordRejection(c.env.DB, box, err.code, at);
      return c.json({ error: err.message, rejected: true, code: err.code, consecutive }, err.status);
    }
    // a jelentés már rögzítve: az állapotgép és a feladat-tükör hibája nem bukhatja el a box kérését (a cron újrapróbálja)
    await advance(c.env.DB, fleet, at).catch(err => console.error('flotta-advance-failed', box.name, err));
    await syncTasks(c.env.DB, fleet, at).catch(err => console.error('flotta-tasks-failed', box.name, err));
    // a token lejárata: a box doctor-ja a lejárat előtt figyelmeztet (forgatás: POST /boxes/:name/token)
    const tok = await c.env.DB.prepare('SELECT expires_at FROM agent_token WHERE id = ?1').bind(box.token_id).first<{ expires_at: string }>();
    // a box a saját szeletét kapja vissza: fedetlen célok, alkalmatlan menedzserek, ember-kell
    const cov = await coverage(c.env.DB, fleet, at, box.name).catch(() => null);
    return c.json({ ok: true, box: box.name, received_at: at.toISOString(), token_expires_at: tok?.expires_at ?? null, ...result, coverage: cov });
  });
}
