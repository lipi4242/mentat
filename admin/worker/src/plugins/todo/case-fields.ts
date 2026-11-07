// The todo_case extension row: validation and the statements that write it.
// Only POST /tasks (kind 'case') creates the row; PATCH /tasks edits it.
import { marked, now } from './store';
import { keys, object, Problem, type Fields } from './types';

const TEXT = ['goal', 'frame', 'next_action', 'waiting_on', 'due_reason', 'brain_ref'] as const;
export const CASE_FIELDS = [...TEXT, 'review_every'];

export function caseFields(input: unknown): Fields {
  const value = object(input); keys(value, CASE_FIELDS);
  const out: Fields = {};
  for (const k of TEXT) {
    if (!(k in value)) continue;
    const v = value[k];
    if (v !== null && (typeof v !== 'string' || v.length > 10000)) throw new Problem(`case.${k} must be text up to 10000 characters, or null`);
    out[k] = v as string | null;
  }
  if ('review_every' in value) {
    const v = value.review_every;
    if (v !== null && (!Number.isInteger(v) || (v as number) < 1 || (v as number) > 3660)) throw new Problem('case.review_every must be 1–3660 days, or null');
    out.review_every = v as number | null;
  }
  return out;
}

/** A case created by a human is confirmed at creation; an agent's case is a proposal. */
export function caseInsert(db: D1Database, id: string, set: Fields, actor: string, human: boolean) {
  const row: Fields = { ...set, task_id: id, confirmed_at: human ? now() : null, confirmed_by: human ? actor : null };
  return db.prepare(`INSERT INTO todo_case (${Object.keys(row).join(',')}) VALUES (${Object.keys(row).map(() => '?').join(',')})`).bind(...Object.values(row));
}

export function caseUpdate(db: D1Database, id: string, set: Fields, op: string) {
  return db.prepare(`UPDATE todo_case SET ${Object.keys(set).map(k => `${k} = ?`).join(',')} WHERE task_id = ? AND ${marked}`)
    .bind(...Object.values(set), id, op);
}

/** Attach the case fields to a task detail when the task is a case. */
export async function caseDetail<T extends { id: string; kind?: string }>(db: D1Database, task: T) {
  if (task.kind !== 'case') return task;
  const row = await db.prepare('SELECT * FROM todo_case WHERE task_id = ?').bind(task.id).first<Record<string, unknown>>();
  const { task_id: _, ...fields } = row ?? {};
  return { ...task, case: fields };
}
