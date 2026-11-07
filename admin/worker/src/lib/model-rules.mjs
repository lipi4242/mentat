// The one definition of a valid config/models.json — what the worker checks at
// load (core/models.ts) and what `npm run model` checks before it writes the
// file. Plain JS on purpose: the CLI runs on a bare Node, like model-sql.mjs.

export const FIELD_TYPES = ['text', 'textarea', 'email', 'date', 'number', 'integer', 'checkbox', 'select', 'ref'];

/** models.fields key → names its fields may not take (the built-in columns). */
export const RESERVED = {
  cases: [
    'id', 'title', 'description', 'status', 'next_action', 'due_at', 'recurrence', 'anchor_at', 'brain_ref',
    'context', 'context_hash', 'extra', 'version', 'created_at', 'updated_at', 'occurrences', 'case_id',
    'open_occurrences', 'events', 'unchanged', 'already_closed',
  ],
};
export const ENTITY_SYSTEM = ['id', 'created_at', 'updated_at'];
const TAKEN = ['meta', 'tokens', 'auth', 'health'];
export const NAME_RE = /^[a-z][a-z0-9_]{0,39}$/;

function fieldErrors(where, fields, reserved, entities) {
  if (!Array.isArray(fields)) return [`${where}: fields must be a list`];
  const out = [];
  const seen = new Set();
  for (const [i, f] of fields.entries()) {
    const at = `${where}.fields[${i}]`;
    if (typeof f !== 'object' || f === null) { out.push(`${at}: must be an object`); continue; }
    if (typeof f.name !== 'string' || !NAME_RE.test(f.name)) out.push(`${at}: name must match ${NAME_RE}`);
    else if (reserved.includes(f.name)) out.push(`${at}: ${f.name} is a built-in field`);
    else if (seen.has(f.name)) out.push(`${at}: ${f.name} is declared twice`);
    else seen.add(f.name);
    if (typeof f.label !== 'string' || !f.label.trim()) out.push(`${at}: label is required`);
    if (!FIELD_TYPES.includes(f.type)) out.push(`${at}: type must be one of ${FIELD_TYPES.join(', ')}`);
    if (f.type === 'select' && (!Array.isArray(f.options) || !f.options.length || f.options.some((o) => typeof o !== 'string'))) {
      out.push(`${at}: a select needs options (a list of strings)`);
    }
    if (f.type === 'ref' && !entities.includes(f.ref)) out.push(`${at}: ref must name a declared entity`);
    for (const k of ['min', 'max']) if (f[k] !== undefined && typeof f[k] !== 'number') out.push(`${at}: ${k} must be a number`);
    if (f.pattern !== undefined) {
      try { new RegExp(f.pattern); } catch { out.push(`${at}: pattern is not a valid regular expression`); }
    }
  }
  return out;
}

/** Every problem with a models document; empty when it can be used. */
export function modelsErrors(m) {
  if (typeof m !== 'object' || m === null) return ['models must be an object'];
  const { fields = {}, entities = [] } = m;
  if (!Array.isArray(entities)) return ['entities must be a list'];
  const names = entities.map((e) => e?.name);
  const out = [];
  for (const [key, list] of Object.entries(fields ?? {})) {
    if (!RESERVED[key]) { out.push(`fields.${key}: only ${Object.keys(RESERVED).join(', ')} can be extended`); continue; }
    out.push(...fieldErrors(`fields.${key}`, list, RESERVED[key], names));
  }
  const seen = new Set();
  for (const [i, e] of entities.entries()) {
    const at = `entities[${i}]`;
    if (typeof e?.name !== 'string' || !NAME_RE.test(e.name)) { out.push(`${at}: name must match ${NAME_RE}`); continue; }
    if (seen.has(e.name)) out.push(`${at}: ${e.name} is declared twice`);
    if (RESERVED[e.name] || TAKEN.includes(e.name)) out.push(`${at}: ${e.name} is taken`);
    seen.add(e.name);
    if (typeof e.label !== 'string' || !e.label.trim()) out.push(`${at}: label is required`);
    out.push(...fieldErrors(at, e.fields, ENTITY_SYSTEM, names));
  }
  return out;
}
