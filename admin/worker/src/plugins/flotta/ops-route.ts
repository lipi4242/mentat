// A javító lépések naplója és kapuja (flotta-menedzser). A végrehajtó sorrendje a célboxon:
// (1) helyi zár → (2) check (ez a fájl) → (3) intent → (4) végrehajtás → (5) result.
// Az intent a végrehajtás ELŐTT rögzül: egy összeomlott lépés így „bizonytalan” marad.
// Mivel a check/intent hívója a cél kizárólagos helyi zárát tartja (v1: csak a saját box),
// a még nyitott szándék biztosan egy halott végrehajtóé → bizonytalan, és a következő
// lépés csak a csak-olvasó `doctor` felmérés lehet. Az újraindítással járó lépések az
// újraindítási keretet (3/óra/ágens) atomikusan, műveleti azonosítóval foglalják.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { advance } from './assign';
import { assertStepFits, assertWindow, execAuth, OP_RE, parseStep } from './exec-auth';
import { RESTART_BUDGET, RESTART_STEPS, STEP_TIMEOUT_MIN, plusMin, toHuman, type Step } from './states';
import { event, getFleet, iso, Problem } from './types';

const OUTCOMES = ['ok', 'failed', 'uncertain', 'busy', 'refused'] as const;
const pending = (db: D1Database, inc: string) =>
  db.prepare(`SELECT count(*) AS n FROM flotta_repair_op WHERE incident_id = ?1 AND state IN ('intent', 'uncertain')`).bind(inc).first<{ n: number }>();

export function registerOps(app: Hono<AppEnv>) {
  app.post('/api/flotta/v1/incidents/:id/ops/check', async c => {
    const { inc, body, box } = await execAuth(c, ['atveve', 'javit', 'ellenorzes']);
    assertWindow(inc, new Date());
    const { step } = parseStep(body, inc);
    await assertStepFits(c.env.DB, box, inc, step);
    if (typeof body.op_id !== 'string' || !OP_RE.test(body.op_id)) throw new Problem('op_id must be an operation id', 400);
    const mustAssess = (await pending(c.env.DB, inc.id))!.n > 0;
    if (mustAssess && step !== 'doctor') throw new Problem('an earlier step has an uncertain outcome: run the read-only doctor first', 409, 'must_assess');
    return c.json({ ok: true, attempt_until: inc.attempt_until, must_assess: mustAssess });
  });

  app.post('/api/flotta/v1/incidents/:id/ops/:op/intent', async c => {
    // ellenőrzésből is: egy félbehagyott ellenőrzés után újra lehet lépni (a nonce ekkor érvénytelen)
    const { inc, body, box } = await execAuth(c, ['atveve', 'javit', 'ellenorzes']);
    const db = c.env.DB, now = new Date(), op = c.req.param('op');
    if (!OP_RE.test(op)) throw new Problem('op id must be an operation id', 400);
    assertWindow(inc, now);
    const { step, target } = parseStep(body, inc);
    await assertStepFits(db, box, inc, step);   // a keretet sem foglalja desktopon
    const had = await db.prepare('SELECT incident_id, state, deadline, fence, step, target FROM flotta_repair_op WHERE id = ?1').bind(op)
      .first<{ incident_id: string; state: string; deadline: string; fence: number; step: string; target: string }>();
    if (had) {   // ugyanaz a szándék újra (hálózati újrapróba): idempotens — de csak ugyanannak a generációnak, ugyanarra
      if (had.incident_id === inc.id && had.state === 'intent' && had.fence === inc.fence && had.step === step && had.target === target) {
        return c.json({ ok: true, deadline: had.deadline, replay: true });
      }
      throw new Problem('operation id already used', 409, 'op_closed');
    }
    // csak ha a fence még a mienk: egy késve érkező, közben elavult kérés nem teheti bizonytalanná az új gazda lépését
    await db.prepare(`UPDATE flotta_repair_op SET state = 'uncertain', finished_at = ?2, summary = 'a végrehajtó nem zárta le (bizonytalan kimenet)'
        WHERE incident_id = ?1 AND state = 'intent'
          AND EXISTS (SELECT 1 FROM flotta_incident WHERE id = ?1 AND fence = ?3 AND claim_hash = ?4)`).bind(inc.id, iso(now), inc.fence, inc.claim_hash).run();
    if ((await pending(db, inc.id))!.n > 0 && step !== 'doctor') throw new Problem('run the read-only doctor first', 409, 'must_assess');
    const restart = RESTART_STEPS.includes(step), deadline = plusMin(now, STEP_TIMEOUT_MIN[step]), agent = inc.agent ?? '';
    // ?2 = ennek a szándéknak az egyedi jele (move_id): a foglalás és a sor CSAK a nyertes átmenetre íródik
    const hourAgo = iso(new Date(now.getTime() - 3600000)), v = `op:${op}`;
    const casOk = `EXISTS (SELECT 1 FROM flotta_incident WHERE id = ?1 AND move_id = ?2)`;
    await db.batch([
      db.prepare(`UPDATE flotta_incident SET state = 'javit', state_at = ?1, nonce_hash = NULL, nonce_fence = NULL, move_id = ?5, version = version + 1
          WHERE id = ?2 AND version = ?3 AND fence = ?4`).bind(iso(now), inc.id, inc.version, inc.fence, v),
      ...(restart ? [db.prepare(`INSERT OR IGNORE INTO flotta_restart_budget (op_id, fleet_id, agent, reserved_at)
          SELECT ?3, ?4, ?5, ?6 WHERE ${casOk} AND (SELECT count(*) FROM flotta_restart_budget WHERE fleet_id = ?4 AND agent = ?5 AND reserved_at > ?7) < ?8`)
        .bind(inc.id, v, op, inc.fleet_id, agent, iso(now), hourAgo, RESTART_BUDGET)] : []),
      db.prepare(`INSERT INTO flotta_repair_op (id, incident_id, fence, principal_id, step, target, state, created_at, deadline)
          SELECT ?3, ?1, ?4, ?5, ?6, ?7, 'intent', ?8, ?9 WHERE ${casOk} AND (?10 = 0 OR EXISTS (SELECT 1 FROM flotta_restart_budget WHERE op_id = ?3))`)
        .bind(inc.id, v, op, inc.fence, inc.claimed_by, step, target, iso(now), deadline, restart ? 1 : 0),
    ]);
    if (await db.prepare('SELECT 1 FROM flotta_repair_op WHERE id = ?1').bind(op).first()) {
      await event(db, inc.id, now, 'op_intent', { op, step, box: box.name });
      return c.json({ ok: true, deadline });
    }
    const cur = await db.prepare('SELECT * FROM flotta_incident WHERE id = ?1').bind(inc.id).first<typeof inc>();
    if (cur!.move_id !== v) throw new Problem('the incident changed meanwhile', 409, 'cas');
    // a CAS átment, a foglalás nem: elfogyott a keret → ember-kell (nem a következő menedzser)
    await toHuman(db, cur!, now, `az újraindítási keret elfogyott (${RESTART_BUDGET}/óra, ${agent})`, 'budget_exhausted');
    throw new Problem('restart budget exhausted for this agent', 409, 'budget');
  });

  app.post('/api/flotta/v1/incidents/:id/ops/:op/result', async c => {
    const db = c.env.DB, now = new Date(), op = c.req.param('op');
    let ctx;
    try { ctx = await execAuth(c, ['atveve', 'javit', 'ellenorzes'], true); } catch (e) {
      // átadás után érkező, késett eredmény: nem hat, de az auditban látszik
      if (e instanceof Problem && e.code === 'stale') await event(db, c.req.param('id'), now, 'stale_result', { op }).catch(() => undefined);
      throw e;
    }
    const { inc, body } = ctx;
    if (!OP_RE.test(op)) throw new Problem('op id must be an operation id', 400);
    const row = await db.prepare('SELECT * FROM flotta_repair_op WHERE id = ?1 AND incident_id = ?2').bind(op, inc.id).first<{ step: Step; state: string; fence: number }>();
    if (!row) {
      // a végrehajtó a szándék ELŐTT várt a dolgozó ágensre, és a keret lejárt: csak napló, nincs keret és állapot
      if (body.outcome !== 'busy') throw new Problem('operation not found', 404);
      const { step, target } = parseStep(body, inc);
      const ins = await db.prepare(`INSERT OR IGNORE INTO flotta_repair_op (id, incident_id, fence, principal_id, step, target, state, created_at, deadline, finished_at, summary)
          VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'busy', ?7, ?7, ?7, 'az ágens dolgozott a kísérleti keret végéig')`).bind(op, inc.id, inc.fence, inc.claimed_by, step, target, iso(now)).run();
      if (!ins.meta.changes) throw new Problem('operation id already used', 409, 'op_closed');
      await event(db, inc.id, now, 'op_busy', { op, step });
      return c.json({ ok: true, state: inc.state });
    }
    if (row.state !== 'intent' || row.fence !== inc.fence) throw new Problem(`operation already closed (${row.state})`, 409, 'op_closed');
    const outcome = body.outcome as typeof OUTCOMES[number];
    if (!OUTCOMES.includes(outcome)) throw new Problem(`outcome must be one of ${OUTCOMES.join(', ')}`, 400);
    const summary = typeof body.summary === 'string' ? body.summary.slice(0, 1000) : null;
    // egy tranzakció: a lépés lezárása CSAK a még érvényes fence + claim mellett hat (átadás közben nem),
    // és a kísérlet-számláló vele együtt nő vagy egyáltalán nem
    const [closed] = await db.batch([
      db.prepare(`UPDATE flotta_repair_op SET state = ?1, finished_at = ?2, summary = ?3 WHERE id = ?4 AND state = 'intent'
          AND EXISTS (SELECT 1 FROM flotta_incident WHERE id = ?5 AND fence = ?6 AND claim_hash = ?7)`)
        .bind(outcome, iso(now), summary, op, inc.id, inc.fence, inc.claim_hash),
      db.prepare(`UPDATE flotta_incident SET attempts = attempts + 1 WHERE id = ?1 AND fence = ?2 AND claim_hash = ?3
          AND EXISTS (SELECT 1 FROM flotta_repair_op WHERE id = ?4 AND state = ?5 AND finished_at = ?6)`)
        .bind(inc.id, inc.fence, inc.claim_hash, op, outcome, iso(now)),
    ]);
    if (!closed.meta.changes) throw new Problem('operation already closed or the claim changed', 409, 'op_closed');
    await event(db, inc.id, now, 'op_result', { op, step: row.step, outcome, assessment: body.assessment ?? null });
    const fresh = (await db.prepare('SELECT * FROM flotta_incident WHERE id = ?1').bind(inc.id).first<typeof inc>())!;
    if (row.step === 'doctor' && body.assessment === 'decided') {
      await db.prepare(`UPDATE flotta_repair_op SET state = 'assessed' WHERE incident_id = ?1 AND state = 'uncertain'`).bind(inc.id).run();
    } else if (row.step === 'doctor' && body.assessment === 'undecidable') {
      await toHuman(db, fresh, now, 'egy bizonytalan lépés hatása a felmérés után sem dönthető el');
    } else if (row.step === 'unquarantine' && outcome === 'refused') {
      await toHuman(db, fresh, now, 'a karantén oka nem gépileg ellenőrizhető (ismeretlen vagy biztonsági ok)');
    }
    await advance(db, (await getFleet(db, inc.fleet_id))!, now, inc.id);   // függő átadás / emberi átvétel most
    const after = await db.prepare('SELECT state FROM flotta_incident WHERE id = ?1').bind(inc.id).first<{ state: string }>();
    return c.json({ ok: true, state: after!.state });
  });
}
