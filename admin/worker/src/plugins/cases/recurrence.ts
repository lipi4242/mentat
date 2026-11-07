// Anchored recurrence (design §3, §10): a series is `anchor_at` plus n steps
// of `recurrence`. Open occurrences are computed on read, never stored.
//
// The one rule the brain's markdown template and the engine's concern package
// must compute identically: a day that does not exist in a month (the 31st,
// or 29 February) falls on that month's last day — and the next month goes
// back to the asked-for day, because every date is derived from the anchor,
// not from the previous date.

export type Recurrence =
  | { kind: 'monthly'; day: number }
  | { kind: 'quarterly'; day: number }
  | { kind: 'yearly'; month: number; day: number }
  | { kind: 'weekly'; weekday: number };

const WEEKDAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
// A runaway loop guard: weekly for 200 years is ~10 400 steps.
const MAX_STEPS = 20000;

const lastDay = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate(); // m is 1-based
const pad = (n: number) => String(n).padStart(2, '0');
const fmt = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;

function parts(iso: string): [number, number, number] {
  const m = DATE_RE.exec(iso);
  if (!m) throw new Error(`not an ISO date: ${iso}`);
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

/** A real calendar date in `YYYY-MM-DD` form — nothing else. */
export function isIsoDate(v: unknown): v is string {
  if (typeof v !== 'string' || !DATE_RE.test(v)) return false;
  const [y, m, d] = parts(v);
  return m >= 1 && m <= 12 && d >= 1 && d <= lastDay(y, m);
}

/** `monthly:<1-31>` | `quarterly:<1-31>` | `yearly:<MM-DD>` | `weekly:<mon..sun>`; null when invalid.
 *  A quarterly series' phase is the anchor's month (anchor 2026-01-20 → Jan, Apr, Jul, Oct). */
export function parseRecurrence(s: unknown): Recurrence | null {
  if (typeof s !== 'string') return null;
  let m = /^(monthly|quarterly):([1-9]|[12]\d|3[01])$/.exec(s);
  if (m) return { kind: m[1] as 'monthly' | 'quarterly', day: Number(m[2]) };
  m = /^yearly:(\d{2})-(\d{2})$/.exec(s);
  if (m) {
    const month = Number(m[1]);
    const day = Number(m[2]);
    // Validated against a leap year, so 02-29 is allowed and 02-30 is not.
    if (month < 1 || month > 12 || day < 1 || day > lastDay(2028, month)) return null;
    return { kind: 'yearly', month, day };
  }
  m = /^weekly:(sun|mon|tue|wed|thu|fri|sat)$/.exec(s);
  if (m) return { kind: 'weekly', weekday: WEEKDAYS.indexOf(m[1]) };
  return null;
}

/** The k-th date of the series (k = 0 is the anchor itself). */
export function nth(anchor: string, r: Recurrence, k: number): string {
  const [y, m, d] = parts(anchor);
  if (r.kind === 'weekly') {
    const t = new Date(Date.UTC(y, m - 1, d + 7 * k));
    return fmt(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
  }
  if (r.kind === 'yearly') return fmt(y + k, r.month, Math.min(r.day, lastDay(y + k, r.month)));
  const months = m - 1 + (r.kind === 'quarterly' ? 3 * k : k);
  const yy = y + Math.floor(months / 12);
  const mm = (months % 12) + 1;
  return fmt(yy, mm, Math.min(r.day, lastDay(yy, mm)));
}

/** Why the anchor cannot start this series, or null if it can. */
export function anchorProblem(anchor: string, r: Recurrence): string | null {
  const [y, m, d] = parts(anchor);
  if (r.kind === 'weekly') {
    const wd = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
    return wd === r.weekday ? null : `anchor_at ${anchor} is not a ${WEEKDAYS[r.weekday]}`;
  }
  const want =
    r.kind === 'yearly'
      ? fmt(y, r.month, Math.min(r.day, lastDay(y, r.month)))
      : fmt(y, m, Math.min(r.day, lastDay(y, m)));
  const label = r.kind === 'yearly' ? `yearly:${pad(r.month)}-${pad(r.day)}` : `${r.kind}:${r.day}`;
  return want === anchor ? null : `anchor_at ${anchor} is not on ${label} (did you mean ${want}?)`;
}

/** The first date of the series strictly after `after` (the anchor when null). */
export function firstOpenAfter(anchor: string, r: Recurrence, after: string | null): string {
  if (after === null) return anchor;
  for (let k = 0; k < MAX_STEPS; k++) {
    const d = nth(anchor, r, k);
    if (d > after) return d;
  }
  throw new Error('recurrence runs past its step limit');
}

/** Every date of the series in [from, until], at most `cap` of them. */
export function seriesBetween(anchor: string, r: Recurrence, from: string, until: string, cap: number): string[] {
  const out: string[] = [];
  for (let k = 0; k < MAX_STEPS && out.length < cap; k++) {
    const d = nth(anchor, r, k);
    if (d > until) break;
    if (d >= from) out.push(d);
  }
  return out;
}

/** True when `date` is one of the series' dates. */
export function onSeries(anchor: string, r: Recurrence, date: string): boolean {
  return seriesBetween(anchor, r, date, date, 1).length === 1;
}

/** The series date whose period holds `date`: the latest one on or before it; null before the anchor. */
export function slotOf(anchor: string, r: Recurrence, date: string): string | null {
  let slot: string | null = null;
  for (let k = 0; k < MAX_STEPS; k++) {
    const d = nth(anchor, r, k);
    if (d > date) return slot;
    slot = d;
  }
  throw new Error('recurrence runs past its step limit');
}

/** Why `due` cannot be the date of the open occurrence `slot`, or null if it can.
 *  The open occurrence may be moved later inside its own period — October due on
 *  the 20th in a monthly:10 series — but not before it, nor onto the next one. */
export function movedDueProblem(anchor: string, r: Recurrence, slot: string, due: string): string | null {
  const next = firstOpenAfter(anchor, r, slot);
  if (due >= slot && due < next) return null;
  return `due_at must be from ${slot} to before ${next} — the earliest open occurrence (${slot}) of this recurring case, moved at most within its own period`;
}
