// Olvasás: a UI (admin-session) vagy egy `flotta:read` token. A beállítás: fleet-config.ts.
import type { Hono } from 'hono';
import { adminEmails, type AppEnv } from '../../types';
import { requireWriter } from '../../lib/guards';
import { coverage } from './coverage';
import { DEFAULT_FLEET, getFleet, minutesBetween, Problem, READ_SCOPE, type Box, type Fleet } from './types';


export function registerStatus(app: Hono<AppEnv>) {
  app.get('/api/flotta/v1/status', async c => {
    const denied = await requireWriter(c, READ_SCOPE); if (denied) return denied;
    const db = c.env.DB, now = new Date();
    await getFleet(db, DEFAULT_FLEET);
    const fleets = (await db.prepare('SELECT * FROM flotta_fleet ORDER BY id').all<Fleet>()).results;
    const boxes = (await db.prepare('SELECT * FROM flotta_box ORDER BY name').all<Box>()).results.map(b => {
      const fleet = fleets.find(f => f.id === b.fleet_id);
      const age = b.last_report_at ? Math.floor(minutesBetween(b.last_report_at, now)) : null;
      return { ...b, release: b.release_json ? JSON.parse(b.release_json) : null, release_json: undefined,
        age_min: age, stale: !b.disabled_at && b.kind !== 'desktop' && (age === null || age >= (fleet?.deadman_min ?? 30)) };
    });
    const agents = (await db.prepare(`SELECT a.*, b.name AS box_name FROM flotta_agent a JOIN flotta_box b ON b.id = a.box_id ORDER BY a.name`)
      .all<{ result_json: string }>()).results.map(a => ({ ...a, result: JSON.parse(a.result_json), result_json: undefined }));
    const incidents = (await db.prepare(`SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id
        ORDER BY i.status = 'open' DESC, coalesce(i.resolved_at, i.opened_at) DESC LIMIT 200`).all<Record<string, unknown>>()).results
      .map(({ claim_hash: _c, nonce_hash: _n, ...rest }) => rest);
    const owner = (f: Fleet) => f.owner_email ?? adminEmails(c.env)[0] ?? null;
    const managers = (await db.prepare(`SELECT m.*, p.handle, p.display_name, p.disabled_at FROM flotta_manager m
        LEFT JOIN todo_principal p ON p.id = m.principal_id ORDER BY m.fleet_id, m.rank, m.id`).all<{ fleet_id: string }>()
      .catch(() => ({ results: [] as Array<{ fleet_id: string }> }))).results;
    const cov = await Promise.all(fleets.map(f => coverage(db, f, now)));
    return c.json({ fleets: fleets.map((f, i) => ({ ...f, effective_owner_email: owner(f), managers: managers.filter(m => m.fleet_id === f.id), coverage: cov[i] })),
      boxes, agents, incidents, now: now.toISOString() });
  });

  app.get('/api/flotta/v1/incidents/:id', async c => {
    const denied = await requireWriter(c, READ_SCOPE); if (denied) return denied;
    const inc = await c.env.DB.prepare(`SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id WHERE i.id = ?1`)
      .bind(c.req.param('id')).first();
    if (!inc) throw new Problem('incident not found', 404);
    const { results } = await c.env.DB.prepare('SELECT * FROM flotta_incident_event WHERE incident_id = ?1 ORDER BY id').bind(c.req.param('id')).all();
    const ops = (await c.env.DB.prepare('SELECT * FROM flotta_repair_op WHERE incident_id = ?1 ORDER BY created_at').bind(c.req.param('id')).all()).results;
    // a claim és a nonce hash-e sem megy ki
    return c.json({ ...inc, claim_hash: undefined, nonce_hash: undefined, events: results, ops });
  });
}
