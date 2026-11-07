// The PM ↔ developer state machine (SPEC §3). Every transition is one guarded
// batch: the event INSERT only runs if the anchor rev, the kind and the
// from-stage still hold, and every other write is conditional on that event.
import type { Context } from 'hono';
import { marked, mutate, now } from './store';
import { Problem, type Fields, type TodoEnv } from './types';
import { getItem, requireDev, requirePm, type Item, type Stage } from './item-store';

export type Move = {
  verb: string; from: Stage[]; by: 'pm' | 'dev'; to: Stage; assignee: string | null;
  item?: Fields; diff?: Record<string, unknown>; recipients?: string[];
  guard?: string; guardArgs?: unknown[]; related?: (op: string) => D1PreparedStatement[];
};

/** Checks that the verb may start from the item's stage and that the caller holds the role. */
export function allowed(c: Context<TodoEnv>, item: Item, verb: string, from: Stage[], by: 'pm' | 'dev') {
  if (!from.includes(item.stage)) throw new Problem(`cannot ${verb} an item that is ${item.stage}`, 409, item);
  if (by === 'pm') requirePm(c, item); else requireDev(c, item);
}

export function transition(c: Context<TodoEnv>, item: Item, m: Move) {
  allowed(c, item, m.verb, m.from, m.by);
  const db = c.env.DB, actor = c.get('principal')!.id, at = now();
  // Invariant 2: the anchor status follows the stage, in the same batch.
  const status = m.to === 'done' ? 'done' : m.to === 'dropped' ? 'dropped' : 'open';
  const set: Fields = { status, assignee_id: m.assignee, assignee_note: null,
    done_at: status === 'done' ? at : null, done_by: status === 'done' ? actor : null };
  const ext: Fields = { stage: m.to, hold_from: m.to === 'hold' ? item.stage : null, ...m.item };
  const guard = `EXISTS (SELECT 1 FROM backlog_item b JOIN todo_task t ON t.id = b.task_id
    WHERE b.task_id = ? AND t.kind = 'item' AND b.stage IN (${m.from.map(() => '?').join(',')}))${m.guard ? ` AND (${m.guard})` : ''}`;
  return mutate(c, item, `item_${m.verb}`, set, {
    diff: { from: item.stage, to: m.to, ...m.diff }, view: getItem,
    recipients: [item.dev_id, ...(m.recipients ?? [])].filter((v): v is string => typeof v === 'string'),
    guard, guardArgs: [item.id, ...m.from, ...(m.guardArgs ?? [])],
    related: op => [db.prepare(`UPDATE backlog_item SET ${Object.keys(ext).map(k => `${k} = ?`).join(',')} WHERE task_id = ? AND ${marked}`)
      .bind(...Object.values(ext), item.id, op), ...(m.related?.(op) ?? [])],
  });
}

const OPEN: Stage[] = ['draft', 'issued', 'taken', 'review'];
/** The simple verbs. `submit`, `accept` and `reject` live in flow-review.ts. */
export const SIMPLE: Record<string, (item: Item, input: { dev?: string; note: string | null }) => Move> = {
  issue: (item, { dev, note }) => ({ verb: 'issue', from: ['draft'], by: 'pm', to: 'issued', assignee: dev!,
    item: { dev_id: dev!, issued_at: now() }, diff: { dev_id: dev, note }, recipients: [dev!],
    guard: 'EXISTS (SELECT 1 FROM backlog_ac WHERE item_id = ? AND removed_at IS NULL)', guardArgs: [item.id] }),
  take: (item, { note }) => ({ verb: 'take', from: ['issued'], by: 'dev', to: 'taken', assignee: item.dev_id,
    item: { taken_at: now() }, diff: { note } }),
  handback: (_item, { note }) => ({ verb: 'handback', from: ['issued', 'taken'], by: 'dev', to: 'draft', assignee: null,
    item: { dev_id: null }, diff: { note } }),
  // The guard pins the exact stage, so the stored hold_from cannot go stale.
  hold: (item, { note }) => ({ verb: 'hold', from: OPEN.includes(item.stage) ? [item.stage] : OPEN,
    by: 'pm', to: 'hold', assignee: null, diff: { note } }),
  resume: (item, { note }) => ({ verb: 'resume', from: ['hold'], by: 'pm', to: item.hold_from ?? 'draft',
    assignee: item.hold_from === 'issued' || item.hold_from === 'taken' ? item.dev_id : null, diff: { note } }),
  drop: (_item, { note }) => ({ verb: 'drop', from: [...OPEN, 'hold'], by: 'pm', to: 'dropped', assignee: null, diff: { note } }),
};
