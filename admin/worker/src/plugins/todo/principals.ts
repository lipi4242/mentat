import type { Hono } from 'hono';
import { adminEmails } from '../../types';
import { hasScope } from '../../lib/guards';
import { event } from './store';
import { newId } from './id';
import { keys, object, Problem, textField, type TodoEnv } from './types';
export function registerPrincipals(app: Hono<TodoEnv>) {
  app.get('/me', async c => c.json(await c.env.DB.prepare('SELECT * FROM todo_principal WHERE id=?').bind(c.get('principal')!.id).first()));
  app.get('/principals', async c => c.json((await c.env.DB.prepare('SELECT * FROM todo_principal ORDER BY display_name').all()).results));
  app.post('/principals', async c => {
    const email = c.get('email'); if (!email) throw new Problem('admin session required', 403);
    const body = object(await c.req.json());
    keys(body, ['kind','handle','display_name','avatar','about','auth_email','agent_token_id','idem_key']);
    const db = c.env.DB, key = textField(body.idem_key, 'idem_key');
    // Stable across bootstrap: the creator namespace is the authenticated email.
    const replay = () => db.prepare('SELECT * FROM todo_principal WHERE created_by = ? AND idem_key = ?').bind(email, key).first();
    const exists = await replay(); if (exists) return c.json(exists);
    const kind = body.kind, authEmail = typeof body.auth_email === 'string' ? body.auth_email.trim().toLowerCase() : null;
    if (!c.get('principal') && (kind !== 'human' || authEmail !== email)) throw new Problem('create your own human principal first', 403);
    const handle = textField(body.handle, 'handle', 64), name = textField(body.display_name, 'display_name');
    if (!/^[a-z0-9_]+$/.test(handle)) throw new Problem('handle must be lowercase letters, digits or underscores');
    if (kind === 'human') {
      if (!authEmail || !adminEmails(c.env).includes(authEmail) || body.agent_token_id != null) throw new Problem('human auth_email must be an admin email; agent_token_id must be null');
    } else if (kind === 'agent') {
      if (body.auth_email != null) throw new Problem('agent auth_email must be null');
      const token = await db.prepare(`SELECT scopes FROM agent_token WHERE id = ? AND active = 1 AND unixepoch(expires_at) > unixepoch('now')`)
        .bind(textField(body.agent_token_id, 'agent_token_id')).first<{ scopes: string }>();
      if (!token || !hasScope(token.scopes, 'todo:write')) throw new Problem('agent_token_id must name a live todo:write token');
    } else throw new Problem('kind must be human or agent');
    const avatar = body.avatar ?? null;
    if (avatar !== null && (typeof avatar !== 'string' || !/^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}$/.test(avatar) || new TextEncoder().encode(avatar).length > 65536)) throw new Problem('avatar must be a raster image data URI up to 64 KB');
    const about = body.about ?? null;
    if (about !== null && (typeof about !== 'string' || about.length > 500)) throw new Problem('about must be text up to 500 characters');
    const id = newId(), actor = c.get('principal')?.id ?? id;
    const row = { id, kind, handle, display_name: name, avatar, about, auth_email: authEmail, agent_token_id: body.agent_token_id ?? null };
    try {
      await db.batch([db.prepare(`INSERT INTO todo_principal (id,kind,handle,display_name,avatar,about,auth_email,agent_token_id,created_by,idem_key) VALUES (?,?,?,?,?,?,?,?,?,?)`)
        .bind(id, kind, handle, name, avatar, about, authEmail, body.agent_token_id ?? null, email, key), event(db, actor, 'principal_created', row, [id])]);
    } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) {
        const won = await replay(); if (won) return c.json(won);
        throw new Problem('handle or credential already mapped');
      }
      throw e;
    }
    return c.json(await db.prepare('SELECT * FROM todo_principal WHERE id=?').bind(id).first(), 201);
  });
}
