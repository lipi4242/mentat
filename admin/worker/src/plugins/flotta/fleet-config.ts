// A flotta beállítása (csak admin-session): a tulajdonos e-mail-címe és a küszöbök.
// A menedzser-listát NEM itt írjuk (flotta-menedzser): egyetlen kiadója a `fleet managers publish`
// (publish.ts, külön config-tokennel), forrása a verziózott fleet-ops/fleet/managers.json.
import type { Hono } from 'hono';
import type { AppEnv } from '../../types';
import { requireAdmin } from '../../lib/guards';
import { getFleet, iso, Problem } from './types';

const THRESHOLDS = ['deadman_min', 'escalate_min', 'debounce_reports', 'repeat_min',
  'max_open_incidents', 'max_open_per_box', 'max_tasks_per_hour', 'max_mails_per_hour'] as const;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function registerFleetConfig(app: Hono<AppEnv>) {
  app.put('/api/flotta/v1/fleets/:id', async c => {
    const denied = await requireAdmin(c); if (denied) return denied;
    const db = c.env.DB, fleet = await getFleet(db, c.req.param('id'));
    if (!fleet) throw new Problem('unknown fleet', 404);
    const body = await c.req.json().catch(() => null) as Record<string, unknown> | null;
    if (!body || typeof body !== 'object') throw new Problem('body must be an object', 400);
    const set: Record<string, string | number | null> = {};
    if ('owner_email' in body) {
      const e = body.owner_email;
      if (e !== null && (typeof e !== 'string' || !EMAIL_RE.test(e))) throw new Problem('owner_email must be an e-mail address or null', 400);
      set.owner_email = e === null ? null : (e as string).trim().toLowerCase();
    }
    for (const k of THRESHOLDS) if (k in body) {
      const v = body[k];
      if (!Number.isInteger(v) || (v as number) < 1 || (v as number) > 100000) throw new Problem(`${k} must be a positive integer`, 400);
      set[k] = v as number;
    }
    if ('managers' in body) throw new Problem('managers are published from fleet-ops (fleet managers publish), not set here', 409);
    if (!Object.keys(set).length) throw new Problem('nothing to change', 400);
    const now = iso(new Date());
    set.updated_at = now;
    const keys = Object.keys(set);
    await db.prepare(`UPDATE flotta_fleet SET ${keys.map((k, i) => `${k} = ?${i + 1}`).join(', ')} WHERE id = ?${keys.length + 1}`).bind(...Object.values(set), fleet.id).run();
    const list = (await db.prepare('SELECT * FROM flotta_manager WHERE fleet_id = ?1 ORDER BY rank, id').bind(fleet.id).all()).results;
    return c.json({ ...(await getFleet(db, fleet.id)), managers: list });
  });
}
