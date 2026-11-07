// Turns a validated PUT body plus the stored row (if any) into the row to
// write — the cross-field rules live here: anchor on the series, due_at of a
// recurring case computed, closed history only as a prefix of the series.
import { anchorProblem, firstOpenAfter, movedDueProblem, nth, parseRecurrence } from './recurrence';
import type { CaseRow } from './store';
import type { CaseInput, Occurrence } from './validate';
import type { FieldDef } from '../../core/fields';

/** Base columns a PUT writes, in a fixed order; the instance's own fields follow them. */
export const BASE_COLS = [
  'title', 'description', 'status', 'next_action', 'due_at', 'recurrence', 'anchor_at',
  'brain_ref', 'context', 'context_hash', 'extra',
] as const;
export const colsFor = (own: readonly FieldDef[]): string[] => [...BASE_COLS, ...own.map((f) => f.name)];
export type Next = Record<string, unknown> & { title: string | null; due_at: string | null; recurrence: string | null; anchor_at: string | null };

/** JSON with object keys sorted, so equal content compares equal as text. */
export function canonical(v: unknown): string {
  const sort = (x: unknown): unknown =>
    Array.isArray(x)
      ? x.map(sort)
      : x && typeof x === 'object'
        ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, sort((x as Record<string, unknown>)[k])]))
        : x;
  return JSON.stringify(sort(v));
}

const sameOccurrences = (a: Occurrence[], b: Occurrence[]) =>
  canonical([...a].sort((x, y) => x.due_at.localeCompare(y.due_at))) === canonical([...b].sort((x, y) => x.due_at.localeCompare(y.due_at)));

/**
 * The row after this PUT, or a 422 message. `stored` is the existing row and
 * its closed occurrences (null on create); `hash` is the context's digest.
 */
export function resolve(
  input: CaseInput,
  stored: { row: CaseRow; occurrences: Occurrence[] } | null,
  hash: string | null | undefined,
  own: readonly FieldDef[] = [],
): { next: Next; occurrences: Occurrence[] } | { error: string } {
  const cols = colsFor(own);
  const base = stored
    ? Object.fromEntries(cols.map((k) => [k, stored.row[k] ?? null]))
    : { ...Object.fromEntries(cols.map((k) => [k, null])), status: 'open', extra: '{}' };
  const next = { ...base } as Next;
  for (const [k, v] of Object.entries(input.fields)) {
    next[k] = k === 'extra' ? canonical(v) : v;
  }
  if (hash !== undefined) next.context_hash = hash;
  if (!next.title) return { error: 'title is required' };
  // An own field may be required only of a new case: rows older than the
  // field have no value, and an unrelated edit of one must not fail on it.
  const missing = stored ? undefined : own.find((f) => f.required && (next[f.name] ?? '') === '');
  if (missing) return { error: `${missing.name} is required` };

  let occurrences = stored?.occurrences ?? [];
  if (input.occurrences) {
    if (stored && !sameOccurrences(input.occurrences, stored.occurrences)) {
      return { error: 'occurrences cannot be rewritten by PUT — close one with POST /api/cases/:id/occurrences' };
    }
    occurrences = input.occurrences;
  }

  const r = parseRecurrence(next.recurrence);
  if (!r) {
    if (!stored && occurrences.length) return { error: 'occurrences need a recurrence' };
    return { next, occurrences };
  }
  if (!next.anchor_at) return { error: 'anchor_at is required with a recurrence (the first due date of the series)' };
  const off = anchorProblem(next.anchor_at, r);
  if (off) return { error: off };
  if (!stored) {
    // Only the earliest open occurrence can ever be closed, so a closed
    // history is always the series' first n dates — anything else is drift.
    const dates = occurrences.map((o) => o.due_at).sort();
    const want = dates.map((_, k) => nth(next.anchor_at!, r, k));
    if (dates.join() !== want.join()) {
      return { error: `occurrences must be the first dates of the series, in order: expected ${want.join(', ') || 'none'}` };
    }
  }
  const last = occurrences.map((o) => o.due_at).sort().at(-1) ?? null;
  const due = firstOpenAfter(next.anchor_at, r, last);
  // due_at is the earliest open occurrence — or that one moved later inside its
  // own period (a first month with its own date). An asked-for date out of that
  // range is refused; a stored one that no longer fits falls back to the series.
  const asked = 'due_at' in input.fields ? (input.fields.due_at as string | null) : (stored?.row.due_at ?? null);
  const problem = asked ? movedDueProblem(next.anchor_at, r, due, asked) : null;
  if (problem && 'due_at' in input.fields) return { error: problem };
  next.due_at = asked && !problem ? asked : due;
  return { next, occurrences };
}
