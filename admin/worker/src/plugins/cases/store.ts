// Reads and statement builders shared by the cases routes.
import type { Context } from 'hono';
import type { AppEnv, Env } from '../../types';
import { onSeries, parseRecurrence, seriesBetween } from './recurrence';
import type { Occurrence } from './validate';

export type CaseRow = {
  id: string;
  title: string;
  status: string;
  description: string | null;
  next_action: string | null;
  due_at: string | null;
  recurrence: string | null;
  anchor_at: string | null;
  brain_ref: string | null;
  context: string | null;
  context_hash: string | null;
  extra: string;
  version: number;
  created_at: string;
  updated_at: string;
  /** The instance's own fields (config/models.json fields.cases). */
  [own: string]: unknown;
};

/** How many open occurrences a single read lists per case, at most. */
export const OPEN_CAP = 60;

export const todayUtc = () => new Date().toISOString().slice(0, 10);

/** The stored row as the API returns it: `extra` as an object, not a string. */
export function toJson(row: CaseRow): Record<string, unknown> {
  return { ...row, extra: JSON.parse(row.extra || '{}') };
}

export async function getCase(DB: Env['DB'], id: string): Promise<CaseRow | null> {
  return DB.prepare(`SELECT * FROM cases_case WHERE id = ?1`).bind(id).first<CaseRow>();
}

export async function getOccurrences(DB: Env['DB'], id: string): Promise<Occurrence[]> {
  const { results } = await DB.prepare(
    `SELECT due_at, status, done_at, note FROM cases_occurrence WHERE case_id = ?1 ORDER BY due_at`,
  )
    .bind(id)
    .all<Occurrence>();
  return results;
}

/** Open dates of a recurring case from its earliest open one up to `until`. */
export function openDates(row: CaseRow, until: string): string[] {
  const r = parseRecurrence(row.recurrence);
  if (!r || !row.anchor_at || !row.due_at) return row.due_at && row.due_at <= until ? [row.due_at] : [];
  const rest = seriesBetween(row.anchor_at, r, row.due_at, until, OPEN_CAP);
  // A moved first open occurrence (off the series, inside its period) comes first.
  if (onSeries(row.anchor_at, r, row.due_at)) return rest;
  return row.due_at <= until ? [row.due_at, ...rest.slice(0, OPEN_CAP - 1)] : [];
}

/** One case in full: the row, its closed and open occurrences, its trail. */
export async function detail(DB: Env['DB'], id: string): Promise<Record<string, unknown> | null> {
  const row = await getCase(DB, id);
  if (!row) return null;
  const { results: events } = await DB.prepare(
    `SELECT id, at, actor, actor_token_id, kind, body FROM cases_event WHERE case_id = ?1 ORDER BY id DESC`,
  )
    .bind(id)
    .all();
  const today = todayUtc();
  const until = row.due_at && row.due_at > today ? row.due_at : today;
  const open = row.recurrence && ['open', 'waiting'].includes(row.status) ? openDates(row, until) : [];
  return { ...toJson(row), occurrences: await getOccurrences(DB, id), open_occurrences: open, events };
}

/** The event insert, guarded so it only lands while the case is at `version`. */
export function eventStmt(c: Context<AppEnv>, id: string, version: number, kind: string, body: unknown): D1PreparedStatement {
  const { actor, actorTokenId } = c.get('actor');
  return c.env.DB.prepare(
    `INSERT INTO cases_event (case_id, actor, actor_token_id, kind, body)
       SELECT ?1, ?2, ?3, ?4, ?5 WHERE (SELECT version FROM cases_case WHERE id = ?1) = ?6`,
  ).bind(id, actor, actorTokenId, kind, JSON.stringify(body), version);
}

/** SHA-256 hex of the mirrored context, so the agent can skip a same upload. */
export async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
