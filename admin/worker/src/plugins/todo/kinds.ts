// Work-kind rules shared by every route: parent kinds, item-only endpoints,
// principal references. Kind and project never change, so these pre-checks
// cannot be invalidated by a concurrent writer.
import type { Context } from 'hono';
import { Problem, type Task, type TodoEnv } from './types';

export const KINDS = ['todo', 'case', 'item'] as const;
export type Kind = typeof KINDS[number];

/** Invariant 3: todo → any parent; case → none; item → none or an item of the same project. */
export async function checkParent(db: D1Database, kind: Kind, parent: string | null, project: string | null = null) {
  if (parent === null) return;
  const row = await db.prepare(`SELECT t.kind, b.project_id FROM todo_task t LEFT JOIN backlog_item b ON b.task_id = t.id WHERE t.id = ?`)
    .bind(parent).first<{ kind: Kind; project_id: string | null }>();
  if (!row) throw new Problem('parent_id does not exist');
  if (kind === 'case') throw new Problem('a case cannot have a parent');
  if (kind === 'item' && (row.kind !== 'item' || row.project_id !== project)) throw new Problem('an item can only be under an item of the same project');
}

export async function projectOf(db: D1Database, task: string) {
  return (await db.prepare('SELECT project_id FROM backlog_item WHERE task_id = ?').bind(task).first<{ project_id: string }>())?.project_id ?? null;
}

/** Invariant 2: generic task writes never touch an item; items use /items. */
export function refuseItem(row: Task, what: string) {
  if (row.kind === 'item') throw new Problem(`${what} is not allowed on a backlog item; use the /items endpoints`, 409);
}

/** An enabled principal by id or handle; the API never lets a request name the actor. */
export async function enabledPrincipal(db: D1Database, ref: unknown, name: string) {
  if (typeof ref !== 'string' || !ref) throw new Problem(`${name} must be a principal id or handle`);
  const row = await db.prepare('SELECT id FROM todo_principal WHERE (id = ? OR handle = ?) AND disabled_at IS NULL').bind(ref, ref).first<{ id: string }>();
  if (!row) throw new Problem(`${name} must be an enabled principal`);
  return row.id;
}

export async function handleId(db: D1Database, name: string, handle: string) {
  const row = await db.prepare('SELECT id FROM todo_principal WHERE handle=?').bind(handle).first<{ id: string }>();
  if (!row) throw new Problem(`${name} must be a known handle`);
  return row.id;
}

export const isHuman = (c: Context<TodoEnv>) => c.get('principal')?.kind === 'human';
export const actorId = (c: Context<TodoEnv>) => c.get('principal')!.id;
