import { isIsoDate, validRule } from './recurrence';
import { keys, object, Problem, textField, type Fields, type Task } from './types';
export const EDITABLE = ['title','description','status','due_date','due_time','planned_date','tz','owner_id',
  'assignee_id','assignee_note','repeat_rule','repeat_from','archived'];
export function fields(input: unknown, create = false): Fields {
  const value = object(input);
  keys(value, create ? [...EDITABLE, 'parent_id', 'position', 'idem_key'] : EDITABLE);
  const out: Fields = {};
  for (const [k, v] of Object.entries(value)) {
    if (k === 'archived') {
      if (v !== 0 && v !== 1) throw new Problem('archived must be 0 or 1');
    } else if (v !== null && typeof v !== 'string') throw new Problem(`${k} must be text or null`);
    out[k] = v as string | number | null;
  }
  for (const k of ['title','tz','owner_id','repeat_from','status','position','idem_key']) {
    if (k in out) textField(out[k], k, k === 'title' ? 1000 : 200);
  }
  for (const k of ['due_date','planned_date']) {
    if (out[k] != null && (!isIsoDate(out[k]) || String(out[k]) < '0100-01-01')) throw new Problem(`${k} must be YYYY-MM-DD`);
  }
  if (out.due_time != null && !/^([01]\d|2[0-3]):[0-5]\d$/.test(String(out.due_time))) throw new Problem('due_time must be HH:MM');
  if (out.status !== undefined && !['open','dropped'].includes(String(out.status))) throw new Problem('status must be open or dropped; use /complete for done');
  if (out.repeat_rule != null && !validRule(out.repeat_rule)) throw new Problem('repeat_rule is invalid');
  if (out.repeat_from !== undefined && !['schedule','completion'].includes(String(out.repeat_from))) throw new Problem('repeat_from must be schedule or completion');
  if (out.tz) { try { new Intl.DateTimeFormat('en', { timeZone: String(out.tz) }); } catch { throw new Problem('tz must be an IANA timezone'); } }
  if ('position' in out) position(out.position);
  if (out.assignee_id !== undefined && out.assignee_id !== null) textField(out.assignee_id, 'assignee_id');
  if (out.description && String(out.description).length > 100000) throw new Problem('description is too long');
  return out;
}
export function position(v: unknown) {
  if (typeof v !== 'string' || !/^[!-~]{1,128}$/.test(v)) throw new Problem('position must be 1–128 printable ASCII characters');
  return v;
}
export async function validateTask(db: D1Database, set: Fields, row?: Task) {
  const next = { ...row, ...set };
  textField(next.title, 'title', 1000);
  if (next.repeat_rule && !next.due_date) throw new Problem('due_date is required with repeat_rule');
  if (next.due_time && !next.due_date) throw new Problem('due_date is required with due_time');
  for (const k of ['owner_id','assignee_id']) {
    const id = next[k as keyof typeof next];
    if (id && (!row || k in set)) {
      if (!await db.prepare('SELECT 1 FROM todo_principal WHERE id = ? AND disabled_at IS NULL').bind(id).first()) throw new Problem(`${k} must be an active principal`);
    }
  }
  if (set.status === 'dropped') Object.assign(set, { assignee_id: null, assignee_note: null, done_at: null, done_by: null });
  if (set.status === 'open') Object.assign(set, { done_at: null, done_by: null });
  if (set.assignee_id === null) set.assignee_note = null;
}
