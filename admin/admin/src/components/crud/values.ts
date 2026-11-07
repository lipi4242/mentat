/** One editable column, rendered as a Form.Item and read back by `normalizeValues`. */
export type FieldSpec = {
  name: string;
  label: string;
  type?: 'text' | 'number' | 'textarea' | 'select' | 'checkbox' | 'ref';
  /** For `select`. Plain strings are used as both value and label. */
  options?: readonly (string | { value: string; label: string })[];
  required?: boolean;
  placeholder?: string;
  /** For `number`. Mirrors a schema CHECK so the field refuses the value
   *  before the round-trip — the worker rejects it with a 400 either way. */
  min?: number;
  /** For `ref`: the resource whose rows are the options (labelled by their first text column). */
  ref?: string;
};

export type FormValues = Record<string, unknown>;

const isBlank = (v: unknown) => v === undefined || v === null || (typeof v === 'string' && !v.trim());

/**
 * Turn an antd form's values into a request body the worker will accept.
 *
 * The create/edit split is not cosmetic. `pick()` on the worker writes every
 * key that is *present*, so:
 *  - on create an untouched field must be absent, or its NULL overrides the
 *    column's SQL default (and trips NOT NULL on e.g. `status`);
 *  - on edit an emptied field must be present as null, or "omitted" reads as
 *    "unchanged" and the old value silently survives the clear.
 */
export function normalizeValues(values: FormValues, fields: readonly FieldSpec[], mode: 'create' | 'edit'): FormValues {
  const out: FormValues = {};
  for (const f of fields) {
    if (!Object.prototype.hasOwnProperty.call(values, f.name)) continue;
    const raw = values[f.name];

    if (f.type === 'checkbox') {
      // Booleans are meaningful even when "false" — never treated as blank.
      // The worker coerces them to SQLite's 0/1 (crud-body.ts).
      if (typeof raw === 'boolean') out[f.name] = raw;
      // A checkbox the user never touched still holds exactly what D1 sent,
      // and an INTEGER-as-boolean column (offer.in_stock) sends 0/1, not
      // true/false. Coerce it back rather than reading "not a boolean" as
      // "cleared": nulling it here wiped the stored value on every unrelated
      // edit of the same row, while the box on screen stayed ticked.
      else if (typeof raw === 'number' && Number.isFinite(raw)) out[f.name] = raw !== 0;
      else if (mode === 'edit') out[f.name] = null;
      continue;
    }

    if (isBlank(raw)) {
      if (mode === 'edit') out[f.name] = null;
      continue;
    }

    if (f.type === 'number') {
      const n = typeof raw === 'number' ? raw : Number(String(raw).replace(',', '.'));
      if (Number.isFinite(n)) out[f.name] = n;
      else if (mode === 'edit') out[f.name] = null;
      continue;
    }

    out[f.name] = typeof raw === 'string' ? raw.trim() : raw;
  }
  return out;
}

/** antd `Select` options from a FieldSpec's shorthand. */
export function selectOptions(f: FieldSpec): { value: string; label: string }[] {
  return (f.options ?? []).map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
}
