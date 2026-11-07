import type { ModelField } from '../../lib/useModels';
import type { FieldSpec } from './values';

/** A declared model field (GET /api/meta) as the generic form's FieldSpec. */
export function toFieldSpec(f: ModelField): FieldSpec {
  const base = { name: f.name, label: f.label, required: f.required };
  switch (f.type) {
    case 'number':
    case 'integer':
      return { ...base, type: 'number', min: f.min };
    case 'textarea':
      return { ...base, type: 'textarea' };
    case 'checkbox':
      return { ...base, type: 'checkbox' };
    case 'select':
      return { ...base, type: 'select', options: f.options ?? [] };
    case 'ref':
      return { ...base, type: 'ref', ref: f.ref };
    case 'date':
      return { ...base, placeholder: 'ÉÉÉÉ-HH-NN' };
    default:
      return base;
  }
}

/** How a stored value reads in a table cell or a description list. */
export function showValue(f: ModelField, v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (f.type === 'checkbox') return v ? 'igen' : 'nem';
  return String(v);
}
