// Who may READ a task. A human (admin session) reads everything. An agent reads a task it is
// involved in: it owns it, holds it, created it, is its item's developer, is named in it or in a
// comment on it, or was ever a recipient of one of its events (so whatever reached its feed can be
// opened). The PM of a project (its default PM) reads every item of that project. Commenting
// needs the same: a comment lands in the reader's context, so whoever cannot see a task cannot
// write into it either.
import type { Context } from 'hono';
import { Problem, type TodoEnv } from './types';
import { isHuman } from './kinds';

/** A WHERE fragment over the todo_task alias `t` and its arguments; `1` for a human. */
export function visibleWhere(c: Context<TodoEnv>, t = 't'): { sql: string; args: string[] } {
  if (isHuman(c)) return { sql: '1', args: [] };
  const me = c.get('principal')!.id;
  const sql = `(${t}.owner_id = ? OR ${t}.assignee_id = ? OR ${t}.created_by = ?
    OR EXISTS (SELECT 1 FROM backlog_item vb JOIN backlog_project vp ON vp.id = vb.project_id
               WHERE vb.task_id = ${t}.id AND (vb.dev_id = ? OR vp.default_pm_id = ?))
    OR EXISTS (SELECT 1 FROM todo_mention vm WHERE vm.principal_id = ? AND (
               (vm.source_kind = 'task' AND vm.source_id = ${t}.id)
               OR (vm.source_kind = 'comment' AND vm.source_id IN (SELECT id FROM todo_comment WHERE task_id = ${t}.id))))
    OR EXISTS (SELECT 1 FROM todo_event ve, json_each(ve.recipients_json) vr WHERE ve.task_id = ${t}.id AND vr.value = ?))`;
  return { sql, args: [me, me, me, me, me, me, me] };
}

/** 404 for a task the caller cannot read: an unseen task does not exist for it. */
export async function requireVisible(c: Context<TodoEnv>, id: string) {
  if (isHuman(c)) return;
  const v = visibleWhere(c);
  const row = await c.env.DB.prepare(`SELECT 1 AS ok FROM todo_task t WHERE t.id = ? AND ${v.sql}`).bind(id, ...v.args).first();
  if (!row) throw new Problem('task not found', 404);
}

/** `/changes?for=` and `/cases/review-due?for=`: an agent asks about itself only. */
export function requireSelf(c: Context<TodoEnv>, principalId: string | null) {
  if (isHuman(c) || principalId === null || principalId === c.get('principal')!.id) return;
  throw new Problem("an agent reads only its own feed (for=<its own handle>)", 403);
}
