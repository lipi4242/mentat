// The instance's own data model (config/models.json; how to extend it:
// agent/EXTENDING.md): extra fields on a plugin's entity, and whole new
// entities. The product ships the file empty and never writes it.
import type { FieldDef } from './fields';
import { ENTITY_SYSTEM as SYSTEM, RESERVED, modelsErrors as rulesErrors } from '../lib/model-rules.mjs';

export type EntityDef = { name: string; label: string; fields: FieldDef[] };
export type Models = { fields: Record<string, FieldDef[]>; entities: EntityDef[] };

/** Plugin entities an instance may add fields to: models.fields key → table. */
export const EXTENSIBLE: Record<string, { table: string; reserved: string[] }> = {
  cases: { table: 'cases_case', reserved: RESERVED.cases },
};

/** Every entity table carries the prefix of the `custom` plugin that owns it. */
export const entityTable = (name: string) => `custom_${name}`;
export const ENTITY_SYSTEM: string[] = SYSTEM;
export const readScopes = (name: string) => [`${name}:read`, `${name}:write`];
export const writeScope = (name: string) => `${name}:write`;

/** Every problem with a models document; empty when it can be used (the rules: lib/model-rules.mjs). */
export const modelsErrors: (m: unknown) => string[] = rulesErrors;

/** The models document, checked; throws naming every problem. */
export function loadModels(m: unknown): Models {
  const errors = modelsErrors(m);
  if (errors.length) throw new Error(`config/models.json: ${errors.join('; ')}`);
  const doc = m as Partial<Models>;
  return { fields: doc.fields ?? {}, entities: doc.entities ?? [] };
}

/** Columns a declared field list expects that `table` does not have yet (a migration not applied). */
export async function missingColumns(DB: D1Database, table: string, names: string[]): Promise<string[]> {
  if (!names.length) return [];
  const { results } = await DB.prepare(`SELECT name FROM pragma_table_info(?1)`).bind(table).all<{ name: string }>();
  const have = new Set(results.map((r) => r.name));
  return names.filter((n) => !have.has(n));
}
