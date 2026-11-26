// Object-level authorization for the todo writes. The token says who the caller is (auth.ts);
// this says whether that caller may touch THIS task. A human (admin session) may do everything.
// An agent may write a task it owns, or one assigned to it; on a backlog item, its PM (the item's
// owner) or its developer. Only the owner (or a human) may hand a task to someone else, move it in
// the tree, or name another owner, so nobody can take over another principal's task.
import type { Context } from 'hono';
import { Problem, type Task, type TodoEnv } from './types';
import { isHuman } from './kinds';

async function devOf(db: D1Database, row: Task) {
  if (row.kind !== 'item') return null;
  return (await db.prepare('SELECT dev_id FROM backlog_item WHERE task_id = ?').bind(row.id).first<{ dev_id: string | null }>())?.dev_id ?? null;
}

/** The caller may change this task's content or state (PATCH, complete, deps, labels). */
export async function requireWriter(c: Context<TodoEnv>, row: Task) {
  if (isHuman(c)) return;
  const me = c.get('principal')!.id;
  if (me === row.owner_id || me === row.assignee_id || me === (await devOf(c.env.DB, row))) return;
  throw new Problem("only the task's owner, its assignee or a human can change it", 403);
}

/** The caller may decide who holds the task or where it sits (reassign, move). */
export function requireOwner(c: Context<TodoEnv>, row: Task) {
  if (isHuman(c) || c.get('principal')!.id === row.owner_id) return;
  throw new Problem("only the task's owner or a human can reassign or move it", 403);
}

/** A new task's owner is its creator, unless a human creates it for someone. */
export function requireOwnOwner(c: Context<TodoEnv>, owner: unknown) {
  if (owner === undefined || isHuman(c) || owner === c.get('principal')!.id) return;
  throw new Problem('an agent creates tasks for itself; put others on it as assignee', 403);
}

/** One agent is never both the PM and the developer of an item: author and checker stay apart. */
export function requireNotOwnDev(c: Context<TodoEnv>, pm: string, dev: string | null) {
  if (!isHuman(c) && dev !== null && pm === dev) throw new Problem("an agent cannot be both the item's PM and its developer", 403);
}
