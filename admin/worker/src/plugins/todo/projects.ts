import type { Hono } from 'hono';
import { event } from './store';
import { newId } from './id';
import { keys, object, Problem, textField, type TodoEnv } from './types';
import { actorId, enabledPrincipal, isHuman } from './kinds';
import { requireImporter } from './import-fill';
export type Project = { id: string; prefix: string; name: string; default_pm_id: string | null; next_number: number };

/** A project by id or by its prefix (any case). */
export async function findProject(db: D1Database, ref: unknown) {
  if (typeof ref !== 'string' || !ref) throw new Problem('project must be a project id or prefix');
  const row = await db.prepare('SELECT * FROM backlog_project WHERE id = ? OR prefix = ?').bind(ref, ref.toUpperCase()).first<Project>();
  if (!row) throw new Problem('project not found');
  return row;
}

export function registerProjects(app: Hono<TodoEnv>) {
  app.get('/projects', async c => c.json((await c.env.DB.prepare('SELECT * FROM backlog_project ORDER BY prefix').all()).results));
  app.post('/projects', async c => {
    // A human, or the Linear importer (todo:import), which creates missing projects.
    if (!isHuman(c)) await requireImporter(c).catch(() => { throw new Problem('only a human or the importer creates a project', 403); });
    const body = object(await c.req.json()); keys(body, ['prefix','name','default_pm','idem_key']);
    const db = c.env.DB, actor = actorId(c), key = textField(body.idem_key, 'idem_key');
    const replay = () => db.prepare('SELECT * FROM backlog_project WHERE created_by = ? AND idem_key = ?').bind(actor, key).first();
    const existing = await replay(); if (existing) return c.json(existing);
    const prefix = textField(body.prefix, 'prefix', 8), name = textField(body.name, 'name');
    if (!/^[A-Z][A-Z0-9]{0,7}$/.test(prefix)) throw new Problem('prefix must be 1–8 capital letters or digits, starting with a letter');
    const pm = body.default_pm == null ? null : await enabledPrincipal(db, body.default_pm, 'default_pm');
    const row = { id: newId(), prefix, name, default_pm_id: pm, created_by: actor, idem_key: key };
    try {
      await db.batch([db.prepare(`INSERT INTO backlog_project (${Object.keys(row).join(',')}) VALUES (?,?,?,?,?,?)`).bind(...Object.values(row)),
        event(db, actor, 'project_created', row, [actor, ...(pm ? [pm] : [])])]);
    } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) { const won = await replay(); if (won) return c.json(won); throw new Problem('prefix already exists'); }
      throw e;
    }
    return c.json(await db.prepare('SELECT * FROM backlog_project WHERE id = ?').bind(row.id).first(), 201);
  });
}
