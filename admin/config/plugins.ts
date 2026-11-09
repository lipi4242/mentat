// Mentat Admin — which plugins this build compiles in. This is PRODUCT
// configuration and lives in git. Everything that belongs to one particular
// installation (title, domains, e-mail addresses, Cloudflare ids) is instance
// data: it comes from the instance file (see config/instance.example.json and
// the README), never from this file.
import type { AdminPlugin } from '../worker/src/core/plugin';
import { loadModels, type Models } from '../worker/src/core/models';
import { makeCasesPlugin } from '../worker/src/plugins/cases';
import { makeCustomPlugin } from '../worker/src/plugins/custom';
import { todoPlugin } from '../worker/src/plugins/todo';
import { flottaPlugin } from '../worker/src/plugins/flotta';
import modelsJson from './models.json';

/**
 * The plugins of a build with this instance model. The cases plugin
 * (worker/src/plugins/cases/) is the template for the next one; `custom`
 * serves the instance's own model (config/models.json — the one file an
 * agent edits to extend the admin).
 */
export function pluginsFor(models: Models): AdminPlugin[] {
  return [makeCasesPlugin(models.fields.cases ?? []), makeCustomPlugin(models), todoPlugin, flottaPlugin];
}

export const MODELS: Models = loadModels(modelsJson);
export const PLUGINS: AdminPlugin[] = pluginsFor(MODELS);

/** Core owns 1–99; every plugin declares its own band. */
export const CORE_BAND: [number, number] = [1, 99];

/**
 * Bands of plugins that were removed from the product. Their migrations stay
 * on disk — an applied migration is never rewritten or deleted, D1 tracks
 * them by name — and the band stays reserved so no new plugin reuses its
 * numbers. A retired band holds the plugin's original migrations plus the
 * one that drops its tables.
 */
export const RETIRED_BANDS: Array<{ id: string; migrationBand: [number, number]; tables: string[] }> = [
  {
    // A retired purchasing plugin: never used in production. Its tables are
    // exported, then dropped by 0101_purchasing_retire.sql.
    id: 'purchasing',
    migrationBand: [100, 199],
    tables: ['purchase_need', 'need_item', 'supplier', 'product', 'offer', 'purchase_intent', 'intent_item', 'allocation'],
  },
];
