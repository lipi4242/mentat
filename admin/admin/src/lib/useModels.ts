import { useApi } from './useApi';

/** A field the instance declared in config/models.json, as GET /api/meta describes it. */
export type ModelField = {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'email' | 'date' | 'number' | 'integer' | 'checkbox' | 'select' | 'ref';
  required?: boolean;
  options?: string[];
  min?: number;
  max?: number;
  pattern?: string;
  ref?: string;
  /** Declared, but its migration has not run yet: not shown, not sent. */
  pending?: boolean;
};

export type ModelEntity = { name: string; label: string; path: string; pending?: boolean; fields: ModelField[] };
export type Models = { fields: Record<string, ModelField[]>; entities: ModelEntity[] };

/**
 * The instance's own model (worker: plugins/custom/meta.ts). The screens draw
 * their extra fields and the "Saját adatok" pages from it, so a field or an
 * entity the agent declares needs no screen code. Anything unexpected reads as
 * "nothing declared" — the product's own fields never depend on it.
 */
export function useModels(): { models: Models; loading: boolean } {
  const { data, loading } = useApi<Partial<Models>>('/api/meta');
  const fields = data && typeof data.fields === 'object' && data.fields ? data.fields : {};
  const entities = Array.isArray(data?.entities) ? data!.entities : [];
  return { models: { fields, entities }, loading };
}

/** The live (migrated) own fields of a plugin entity, e.g. `ownFields(models, 'cases')`. */
export const ownFields = (m: Models, key: string): ModelField[] =>
  (Array.isArray(m.fields[key]) ? m.fields[key] : []).filter((f) => !f.pending);
