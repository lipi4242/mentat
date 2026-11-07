// The `custom` plugin: the instance's own data model (config/models.json;
// how to extend it: agent/EXTENDING.md). Each declared entity is a
// table `custom_<name>` behind the core's generic CRUD; GET /api/meta tells
// the screen and the agent what is declared. Band 900–999 is the instance's:
// the product never ships a migration there, so an upgrade cannot collide.
import type { Hono, MiddlewareHandler } from 'hono';
import type { AppEnv } from '../../types';
import type { AdminPlugin } from '../../core/plugin';
import { registerCrud } from '../../core/crud';
import { fieldsProblem } from '../../core/fields';
import { EXTENSIBLE, entityTable, missingColumns, readScopes, writeScope, type EntityDef, type Models } from '../../core/models';
import { registerMeta } from './meta';

function registerEntity(app: Hono<AppEnv>, e: EntityDef) {
  const table = entityTable(e.name);
  const names = e.fields.map((f) => f.name);
  // Declared but not migrated: a 503 that says so, not a 500 from SQLite.
  const guard: MiddlewareHandler<AppEnv> = async (c, next) => {
    const missing = await missingColumns(c.env.DB, table, ['id', ...names]);
    if (missing.length) {
      const what = missing.includes('id') ? `table ${table}` : missing.join(', ');
      return c.json({ error: `not migrated yet: ${what} — apply the migration that adds it` }, 503);
    }
    await next();
  };
  app.use(`/api/${e.name}`, guard);
  app.use(`/api/${e.name}/*`, guard);
  const required = e.fields.filter((f) => f.required).map((f) => f.name);
  registerCrud(app, {
    path: e.name,
    table,
    columns: names,
    scope: writeScope(e.name),
    readScope: readScopes(e.name),
    required,
    notNull: required,
    orderBy: 'created_at DESC',
    filterable: names,
    validate: (body, mode) => fieldsProblem(e.fields, body, mode),
  });
}

export function makeCustomPlugin(models: Models): AdminPlugin {
  return {
    id: 'custom',
    migrationBand: [900, 999],
    tables: models.entities.map((e) => entityTable(e.name)),
    extends: Object.keys(models.fields).map((k) => EXTENSIBLE[k].table),
    registerRoutes(app) {
      registerMeta(app, models);
      for (const e of models.entities) registerEntity(app, e);
    },
  };
}
