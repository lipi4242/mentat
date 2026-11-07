// One declared field (config/models.json) and how a value for it is checked.
// The same definition drives the column (scripts/lib/model-sql.mjs), the API
// validation here, and the form on the screen (GET /api/meta).

import { FIELD_TYPES } from '../lib/model-rules.mjs';
export { FIELD_TYPES };
export type FieldType = (typeof FIELD_TYPES)[number];

export type FieldDef = {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  /** select: the allowed values. */
  options?: string[];
  /** number / integer: inclusive bounds. */
  min?: number;
  max?: number;
  /** text / textarea / email: a regular expression the whole value must match. */
  pattern?: string;
  /** ref: the entity (config/models.json entities[].name) this field points at. */
  ref?: string;
};

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isDate(v: unknown): boolean {
  const m = typeof v === 'string' ? DATE_RE.exec(v) : null;
  if (!m) return false;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return d.getUTCMonth() === Number(m[2]) - 1 && d.getUTCDate() === Number(m[3]);
}

/** Why `v` is not a valid value for `f`, or null. `null` itself is always valid here — `required` is the caller's call. */
export function fieldProblem(f: FieldDef, v: unknown): string | null {
  if (v === null) return null;
  const n = f.name;
  switch (f.type) {
    case 'number':
    case 'integer': {
      if (typeof v !== 'number' || !Number.isFinite(v)) return `${n} must be a number`;
      if (f.type === 'integer' && !Number.isInteger(v)) return `${n} must be a whole number`;
      if (f.min !== undefined && v < f.min) return `${n} must be at least ${f.min}`;
      if (f.max !== undefined && v > f.max) return `${n} must be at most ${f.max}`;
      return null;
    }
    case 'checkbox':
      return typeof v === 'boolean' || v === 0 || v === 1 ? null : `${n} must be true or false`;
    case 'date':
      return isDate(v) ? null : `${n} must be a YYYY-MM-DD date`;
    case 'select':
      return typeof v === 'string' && (f.options ?? []).includes(v) ? null : `${n} must be one of ${(f.options ?? []).join(', ')}`;
    case 'ref':
      return typeof v === 'string' && v.length > 0 ? null : `${n} must be the id of a ${f.ref} row`;
    default: {
      if (typeof v !== 'string') return `${n} must be text`;
      if (f.type === 'email' && !EMAIL_RE.test(v)) return `${n} must be an e-mail address`;
      if (f.pattern && !new RegExp(`^(?:${f.pattern})$`).test(v)) return `${n} does not match ${f.pattern}`;
      return null;
    }
  }
}

/**
 * Check the declared fields present in `body`. On create, a required field
 * must be present and non-empty; on update an absent key means "unchanged",
 * but a required one cannot be cleared.
 */
export function fieldsProblem(defs: readonly FieldDef[], body: Record<string, unknown>, mode: 'create' | 'update'): string | null {
  for (const f of defs) {
    const has = Object.prototype.hasOwnProperty.call(body, f.name);
    const v = body[f.name];
    const empty = v === null || v === undefined || (typeof v === 'string' && !v.trim());
    if (f.required && empty && (has || mode === 'create')) return `${f.name} is required`;
    if (!has) continue;
    const p = fieldProblem(f, v);
    if (p) return p;
  }
  return null;
}
