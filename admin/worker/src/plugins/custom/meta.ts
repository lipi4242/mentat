// GET /api/meta — what this installation declares beyond the product: the
// instance's own case fields and entities, with the scopes that reach them.
// The screen draws its forms and lists from this; the agent reads it to know
// what it may write. A token sees only what its scopes reach; a field whose
// migration has not run yet is listed with `pending: true`.
import type { Context, Hono } from 'hono';
import type { AppEnv } from '../../types';
import { hasAdminSession, hasScope, resolveAgentToken } from '../../lib/guards';
import { EXTENSIBLE, entityTable, missingColumns, readScopes, writeScope, type Models } from '../../core/models';
import type { FieldDef } from '../../core/fields';

async function withPending(c: Context<AppEnv>, table: string, fields: FieldDef[]) {
  const missing = new Set(await missingColumns(c.env.DB, table, fields.map((f) => f.name)));
  return fields.map((f) => (missing.has(f.name) ? { ...f, pending: true } : f));
}

export function registerMeta(app: Hono<AppEnv>, models: Models) {
  app.get('/api/meta', async (c) => {
    const supplied = c.req.header('X-Mentat-Token') ?? '';
    let may: (scopes: string[]) => boolean;
    if (supplied) {
      const tok = await resolveAgentToken(c.env.DB, supplied);
      if (!tok) return c.json({ error: 'unauthorized' }, 401);
      may = (scopes) => scopes.some((s) => hasScope(tok.scopes, s));
    } else if (await hasAdminSession(c)) {
      may = () => true;
    } else {
      return c.json({ error: 'unauthorized' }, 401);
    }
    const fields: Record<string, FieldDef[]> = {};
    for (const [key, list] of Object.entries(models.fields)) {
      if (may(readScopes(key))) fields[key] = await withPending(c, EXTENSIBLE[key].table, list);
    }
    const entities = [];
    for (const e of models.entities) {
      if (!may(readScopes(e.name))) continue;
      const table = entityTable(e.name);
      const exists = !(await missingColumns(c.env.DB, table, ['id'])).length;
      entities.push({
        name: e.name,
        label: e.label,
        path: `/api/${e.name}`,
        scopes: { read: readScopes(e.name), write: writeScope(e.name) },
        ...(exists ? {} : { pending: true }),
        fields: exists ? await withPending(c, table, e.fields) : e.fields.map((f) => ({ ...f, pending: true })),
      });
    }
    return c.json({ fields, entities });
  });
}
