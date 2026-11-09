// Ellenőrzés és lezárás (flotta-menedzser). Csak akkor indulhat, ha minden művelet lezárult vagy
// fel van mérve. A Worker nonce-t ad a fence-hez (az incidens generációjához) kötve; a
// végrehajtó a célon FRISS képesség-próbát futtat, és a nonce-ot az ágens processzének
// boot-azonosítójával adja vissza. Csak a zöld, nonce-ot hordozó eredmény zár; egy régi
// (előző nonce-os vagy előző generációs) eredmény nem. Lezáráskor minden token érvénytelen.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { hashToken } from '../../lib/tokens';
import { assertWindow, execAuth } from './exec-auth';
import { move, plusMin, secret, STEP_TIMEOUT_MIN } from './states';
import { iso, Problem, type Row } from './types';

/** true, ha a nonce kiadása (az ellenőrzésbe lépés, `state_at`) után jött jelentés zöldnek mutatja a célt. */
async function proven(db: D1Database, inc: Row): Promise<true | string> {
  const since = inc.state_at ?? '';
  if (!inc.agent) {
    const b = await db.prepare('SELECT last_report_at FROM flotta_box WHERE id = ?1').bind(inc.box_id).first<{ last_report_at: string | null }>();
    return b?.last_report_at && b.last_report_at > since ? true : 'the box has not reported since';
  }
  const a = await db.prepare('SELECT last_seen_at, result_json FROM flotta_agent WHERE fleet_id = ?1 AND name = ?2 AND box_id = ?3')
    .bind(inc.fleet_id, inc.agent, inc.box_id).first<{ last_seen_at: string; result_json: string }>();
  if (!a || !(a.last_seen_at > since)) return 'no report of the agent since';
  let red: Array<{ check: string }> = [];
  try { red = JSON.parse(a.result_json).red ?? []; } catch { return 'unreadable report'; }
  return red.some(r => r.check === inc.check_key) ? `the report still shows ${inc.check_key} red` : true;
}

export function registerVerify(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/incidents/:id/verify/start', async c => {
    const { inc } = await execAuth(c, ['atveve', 'javit', 'ellenorzes']);
    const db = c.env.DB, now = new Date();
    assertWindow(inc, now);
    const open = await db.prepare(`SELECT state, count(*) AS n FROM flotta_repair_op WHERE incident_id = ?1 AND state IN ('intent', 'uncertain') GROUP BY state`)
      .bind(inc.id).all<{ state: string; n: number }>();
    if (open.results.some(r => r.state === 'intent')) throw new Problem('an operation is still open', 409, 'open_ops');
    if (open.results.some(r => r.state === 'uncertain')) throw new Problem('an uncertain step is not assessed yet (run doctor)', 409, 'must_assess');
    const nonce = secret(), until = plusMin(now, STEP_TIMEOUT_MIN.postcheck);
    const ok = await move(db, inc, 'ellenorzes', now, { nonce_hash: await hashToken(nonce), nonce_fence: inc.fence },
      { kind: 'verify_start', body: { fence: inc.fence } });
    if (!ok) throw new Problem('the incident changed meanwhile', 409, 'cas');
    return c.json({ nonce, until: inc.attempt_until! < until ? inc.attempt_until : until });
  });

  app.post('/api/flotta/v1/incidents/:id/verify/result', async c => {
    const { inc, body } = await execAuth(c, ['ellenorzes']);
    const db = c.env.DB, now = new Date();
    assertWindow(inc, now);   // a keret lejárta után az átadás jön, nem a lezárás
    if (typeof body.nonce !== 'string' || !inc.nonce_hash || inc.nonce_fence !== inc.fence || await hashToken(body.nonce) !== inc.nonce_hash) {
      throw new Problem('stale or unknown verification nonce', 409, 'stale');
    }
    const boot = typeof body.boot_id === 'string' ? body.boot_id.trim() : '';
    if (!boot || boot.length > 200) throw new Problem('boot_id is required (the agent process boot identity)', 400);
    const summary = typeof body.summary === 'string' ? body.summary.slice(0, 1000) : null;
    if (body.green === true) {
      // a zöldet nem a claim gazdája igazolja: kell egy, a nonce kiadása UTÁN érkezett box-jelentés,
      // amelyben ez az ellenőrzés zöld (box-célnál maga a jelentés), különben 409 unproven
      const proof = await proven(db, inc);
      if (proof !== true) throw new Problem(`not proven by a box report after the nonce: ${proof}`, 409, 'unproven');
      const ok = await move(db, inc, 'megoldva', now, { verified_boot_id: boot, resolve_note: `ellenőrizve (nonce, ${iso(now)})` },
        { kind: 'verified', body: { boot_id: boot, summary } });
      if (!ok) throw new Problem('the incident changed meanwhile', 409, 'cas');
      return c.json({ state: 'megoldva' });
    }
    const ok = await move(db, inc, 'javit', now, { nonce_hash: null, nonce_fence: null }, { kind: 'verify_red', body: { boot_id: boot, summary } });
    if (!ok) throw new Problem('the incident changed meanwhile', 409, 'cas');
    return c.json({ state: 'javit' });
  });
}
