// `npm run model`: the request → the new config/models.json document. Pure
// (no I/O); scripts/model.mjs reads and writes the file. Every branch on a
// type or a flag ends in an explicit error — nothing unknown is ignored.
import { FIELD_TYPES, modelsErrors } from '../../src/lib/model-rules.mjs';

export class UsageError extends Error {}
const fail = (msg) => { throw new UsageError(msg); };

const VALUE_FLAGS = ['type', 'label', 'min', 'max', 'options', 'ref', 'pattern', 'repo'];
const BOOL_FLAGS = ['required', 'check', 'no-probe', 'help'];
const LIST_FLAGS = ['field'];
const ALIAS = { ugyek: 'cases' };

/** argv → { cmd, rest, flags, fields }. Unknown flags and missing values are errors. */
export function parseArgs(argv) {
  const [cmd, ...tail] = argv;
  const flags = {};
  const fields = [];
  const rest = [];
  for (let i = 0; i < tail.length; i++) {
    const a = tail[i];
    if (!a.startsWith('--')) { rest.push(a); continue; }
    const k = a.slice(2);
    if (BOOL_FLAGS.includes(k)) flags[k] = true;
    else if (VALUE_FLAGS.includes(k) || LIST_FLAGS.includes(k)) {
      const v = tail[++i];
      if (v === undefined || v.startsWith('--')) fail(`--${k} needs a value`);
      if (LIST_FLAGS.includes(k)) fields.push(v); else flags[k] = v;
    } else fail(`unknown option --${k}`);
  }
  return { cmd, rest, flags, fields };
}

const num = (k, v) => (Number.isFinite(Number(v)) && v !== '' ? Number(v) : fail(`--${k} must be a number, got "${v}"`));
const nice = (n) => n.charAt(0).toUpperCase() + n.slice(1).replace(/_/g, ' ');

/** A field object from its parts; options that do not fit the type are errors. */
export function makeField(name, { type, label, required, min, max, options, ref, pattern }) {
  if (!FIELD_TYPES.includes(type)) fail(`unknown type "${type}" — one of: ${FIELD_TYPES.join(', ')}`);
  const f = { name, label: label ?? nice(name), type };
  const only = (what, ok, v) => { if (v !== undefined && !ok.includes(type)) fail(`${what} does not apply to type ${type} (${ok.join('/')} only)`); };
  only('min/max', ['number', 'integer'], min ?? max);
  only('options', ['select'], options);
  only('ref', ['ref'], ref);
  only('pattern', ['text', 'textarea', 'email'], pattern);
  if (type === 'select' && !options) fail('a select needs options (--options a,b,c)');
  if (type === 'ref' && !ref) fail('a ref needs the entity it points at (--ref <entity>)');
  if (required) f.required = true;
  if (min !== undefined) f.min = num('min', min);
  if (max !== undefined) f.max = num('max', max);
  if (options) f.options = String(options).split(/[,|]/).map((s) => s.trim()).filter(Boolean);
  if (ref) f.ref = ref;
  if (pattern) f.pattern = pattern;
  return f;
}

/** `name:type[:required|min=0|max=9|options=a|b|ref=x|label=Text]…` */
export function parseFieldSpec(spec) {
  const [name, type, ...parts] = spec.split(':');
  if (!name || !type) fail(`--field "${spec}": expected name:type[:required|min=N|max=N|options=a|b|ref=entity|label=Text]`);
  const o = { type };
  for (const p of parts) {
    const [k, ...v] = p.split('=');
    if (k === 'required' && !v.length) o.required = true;
    else if (['min', 'max', 'options', 'ref', 'label', 'pattern'].includes(k) && v.length) o[k] = v.join('=');
    else fail(`--field "${spec}": unknown part "${p}"`);
  }
  return makeField(name, o);
}

/** `--ref ugyfel` → the entity it names: exactly that, or the one whose name starts with it. */
export function resolveRef(models, key) {
  const names = models.entities.map((e) => e.name);
  if (names.includes(key)) return key;
  const hits = names.filter((n) => n.startsWith(key));
  if (hits.length === 1) return hits[0];
  return fail(hits.length ? `--ref ${key} is ambiguous: ${hits.join(', ')}` : `--ref ${key}: no such entity (declared: ${names.join(', ') || 'none'}) — create it first with: npm run model -- new ${key} …`);
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const finish = (models, out) => {
  const bad = modelsErrors(out.models);
  if (bad.length) fail(`the result would not be a valid models.json:\n  ${bad.join('\n  ')}`);
  return { ...out, changed: !same(models, out.models) };
};

/** add-field <model> <name> … → { models, kind, target, field, slug, changed }. */
export function addField(models, [model, name, extra], flags) {
  if (!model || !name || extra !== undefined) fail('usage: npm run model -- add-field <model> <field> --type T [--label L] [--min N] [--required]');
  if (!flags.type) fail(`add-field needs --type (${FIELD_TYPES.join(', ')})`);
  const key = ALIAS[model] ?? model;
  const field = makeField(name, { ...flags, ref: flags.ref && resolveRef(models, flags.ref) });
  const next = structuredClone(models);
  let list;
  if (next.fields[key] !== undefined || key === 'cases') list = (next.fields[key] ??= []);
  else list = next.entities.find((e) => e.name === key)?.fields ?? fail(`unknown model "${model}" — cases, or one of: ${models.entities.map((e) => e.name).join(', ') || '(no own entities yet)'}`);
  const old = list.find((f) => f.name === name);
  if (old && !same(old, field)) fail(`${model}.${name} is already declared differently (${JSON.stringify(old)}) — changing a field is a hand-written migration, not this command`);
  if (!old) list.push(field);
  const entity = key === 'cases' ? null : next.entities.find((e) => e.name === key);
  return finish(models, { models: next, kind: 'field', target: { name: key, label: entity?.label ?? 'Ügyek' }, field, slug: `${key}_${name}`.slice(0, 41) });
}

/** new <entity> --label L --field spec… [--ref other] → same shape. */
export function newEntity(models, [name, extra], flags, specs) {
  if (!name || extra !== undefined) fail('usage: npm run model -- new <entity> --label L --field name:type[:required] … [--ref other-entity]');
  if (ALIAS[name]) fail(`"${name}" is taken`);
  const fields = specs.map(parseFieldSpec);
  if (flags.ref) {
    const target = resolveRef(models, flags.ref);
    fields.push(makeField(flags.ref.replace(/[^a-z0-9_]/g, '_'), { type: 'ref', ref: target, required: true, label: nice(flags.ref) }));
  }
  if (!fields.length) fail('new needs at least one --field (or --ref)');
  const entity = { name, label: flags.label ?? nice(name), fields };
  const old = models.entities.find((e) => e.name === name);
  if (old && !same(old, entity)) fail(`${name} is already declared differently — extend it with: npm run model -- add-field ${name} …`);
  const next = structuredClone(models);
  if (!old) next.entities.push(entity);
  return finish(models, { models: next, kind: 'entity', target: { name, label: entity.label }, field: null, slug: name.slice(0, 41) });
}
