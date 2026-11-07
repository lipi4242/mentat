// The cases plugin: one entity, the case, with anchored recurrence. The
// template every other plugin copies: a read side, a write side, a close
// action, and a migration band of its own (config/plugins.ts).
import type { AdminPlugin } from '../../core/plugin';
import type { FieldDef } from '../../core/fields';
import { registerReads } from './read';
import { registerPut } from './put';
import { registerClose } from './close';

/** `own`: the instance's own case fields (config/models.json fields.cases). */
export function makeCasesPlugin(own: readonly FieldDef[] = []): AdminPlugin {
  return {
    id: 'cases',
    migrationBand: [200, 299],
    tables: ['cases_case', 'cases_occurrence', 'cases_event'],
    registerRoutes(app) {
      // Reads first: `/api/cases/due` and `/api/cases/events` must win over
      // `/api/cases/:id`.
      registerReads(app);
      registerPut(app, own);
      registerClose(app);
    },
  };
}
