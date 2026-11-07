// Field-level validation of cases plugin request bodies. Every rejection is a
// 422 that names the field: the writer is usually an agent, and a message it
// can act on is the difference between a fix and a retry loop.
import { isIsoDate, parseRecurrence } from './recurrence';
import { fieldProblem, type FieldDef } from '../../core/fields';

export const STATUSES = ['open', 'waiting', 'done', 'dropped'] as const;
export const OCC_STATUSES = ['done', 'skipped'] as const;
/** Crockford base32, 26 chars, first char ≤ 7 (the 128-bit ceiling). */
export const ULID_RE = /^[0-7][0-9A-HJKMNP-TV-Z]{25}$/;

const TEXT = ['title', 'description', 'next_action', 'brain_ref', 'context'] as const;
const DATES = ['due_at', 'anchor_at'] as const;
/** The tracked fields a PUT may set (the brain template's frontmatter names). */
export const FIELDS = [...TEXT, ...DATES, 'status', 'recurrence', 'extra'] as const;
export type Field = (typeof FIELDS)[number];
const PUT_KEYS = [...FIELDS, 'occurrences', 'version', 'case_id'];

export type Occurrence = { due_at: string; status: 'done' | 'skipped'; done_at: string | null; note: string | null };
/** `fields` holds the base fields and the instance's own ones (config/models.json fields.cases). */
export type CaseInput = { fields: Record<string, unknown>; occurrences?: Occurrence[]; version?: number };

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const unknownKeys = (body: Record<string, unknown>, allowed: Set<string>) => Object.keys(body).filter((k) => !allowed.has(k));

/** One closed occurrence, as the close endpoint and a migration PUT take it. */
export function checkOccurrence(o: unknown, where = ''): Occurrence | string {
  if (!isObject(o)) return `${where}must be an object`;
  const bad = unknownKeys(o, new Set(['due_at', 'status', 'done_at', 'note']));
  if (bad.length) return `${where}unknown field(s): ${bad.join(', ')}`;
  if (!isIsoDate(o.due_at)) return `${where}due_at must be a YYYY-MM-DD date`;
  const status = o.status ?? 'done';
  if (!OCC_STATUSES.includes(status as never)) return `${where}status must be done or skipped`;
  if (o.done_at != null && !isIsoDate(o.done_at)) return `${where}done_at must be a YYYY-MM-DD date`;
  if (o.note != null && typeof o.note !== 'string') return `${where}note must be text`;
  return { due_at: o.due_at, status: status as Occurrence['status'], done_at: (o.done_at as string) ?? null, note: (o.note as string) ?? null };
}

/** Validate a PUT body in isolation (cross-field rules need the stored row). */
export function checkPut(body: unknown, id: string, own: readonly FieldDef[] = []): CaseInput | { error: string } {
  if (!ULID_RE.test(id)) return { error: 'id must be a ULID (26 chars, Crockford base32, upper case)' };
  if (!isObject(body)) return { error: 'body must be a JSON object' };
  const bad = unknownKeys(body, new Set([...PUT_KEYS, ...own.map((f) => f.name)]));
  if (bad.length) return { error: `unknown field(s): ${bad.join(', ')}` };
  if (body.case_id !== undefined && body.case_id !== id) return { error: 'case_id must equal the id in the URL' };
  const fields: CaseInput['fields'] = {};
  for (const k of TEXT) {
    if (!(k in body)) continue;
    const v = body[k];
    if (v !== null && typeof v !== 'string') return { error: `${k} must be text or null` };
    fields[k] = v;
  }
  if ('title' in fields && (typeof fields.title !== 'string' || !fields.title.trim())) return { error: 'title must not be empty' };
  for (const k of DATES) {
    if (!(k in body)) continue;
    if (body[k] !== null && !isIsoDate(body[k])) return { error: `${k} must be a YYYY-MM-DD date or null` };
    fields[k] = body[k];
  }
  if ('status' in body) {
    if (!STATUSES.includes(body.status as never)) return { error: `status must be one of ${STATUSES.join(', ')}` };
    fields.status = body.status;
  }
  if ('recurrence' in body) {
    if (body.recurrence !== null && !parseRecurrence(body.recurrence)) {
      return { error: 'recurrence must be monthly:<1-31>, quarterly:<1-31>, yearly:<MM-DD>, weekly:<mon..sun> or null' };
    }
    fields.recurrence = body.recurrence;
  }
  if ('extra' in body) {
    if (!isObject(body.extra)) return { error: 'extra must be a JSON object' };
    fields.extra = body.extra;
  }
  for (const f of own) {
    if (!(f.name in body)) continue;
    const problem = fieldProblem(f, body[f.name]);
    if (problem) return { error: problem };
    const v = body[f.name];
    // D1 binds no booleans: a checkbox is stored as 0/1.
    fields[f.name] = typeof v === 'boolean' ? (v ? 1 : 0) : v;
  }
  const out: CaseInput = { fields };
  if ('version' in body) {
    if (!Number.isInteger(body.version) || (body.version as number) < 1) return { error: 'version must be a positive integer' };
    out.version = body.version as number;
  }
  if ('occurrences' in body) {
    if (!Array.isArray(body.occurrences)) return { error: 'occurrences must be a list' };
    const list: Occurrence[] = [];
    for (const [i, o] of body.occurrences.entries()) {
      const r = checkOccurrence(o, `occurrences[${i}]: `);
      if (typeof r === 'string') return { error: r };
      list.push(r);
    }
    out.occurrences = list;
  }
  return out;
}

/** Validate a close request (POST /api/cases/:id/occurrences). */
export function checkClose(body: unknown): Occurrence | { error: string } {
  const r = checkOccurrence(body);
  return typeof r === 'string' ? { error: r } : r;
}
