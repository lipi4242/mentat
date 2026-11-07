// The case as the worker's cases plugin returns it, and how the UI names
// its states. Field names are the brain template's frontmatter names.
import type { CaseEvent } from './CaseEvents';

export type CaseStatus = 'open' | 'waiting' | 'done' | 'dropped';

export type CaseRow = {
  id: string;
  title: string;
  status: CaseStatus;
  description: string | null;
  next_action: string | null;
  due_at: string | null;
  recurrence: string | null;
  anchor_at: string | null;
  brain_ref: string | null;
  context?: string | null;
  context_hash: string | null;
  extra: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
  /** The instance's own fields (config/models.json fields.cases, via GET /api/meta). */
  [own: string]: unknown;
};

export type Occurrence = { due_at: string; status: 'done' | 'skipped'; done_at: string | null; note: string | null };

export type CaseDetail = CaseRow & {
  occurrences: Occurrence[];
  open_occurrences: string[];
  events: CaseEvent[];
};

export const STATUS: Record<CaseStatus, { label: string; color: string }> = {
  open: { label: 'nyitott', color: 'blue' },
  waiting: { label: 'várakozik', color: 'orange' },
  done: { label: 'kész', color: 'green' },
  dropped: { label: 'elejtve', color: 'default' },
};

const WEEKDAY: Record<string, string> = {
  mon: 'hétfőn', tue: 'kedden', wed: 'szerdán', thu: 'csütörtökön', fri: 'pénteken', sat: 'szombaton', sun: 'vasárnap',
};

// The day's suffix as it is read aloud: 1-jén, 3-án, 10-én, 20-án, 31-én.
const ON_DAY: Record<string, string> = {
  1: 'jén', 2: 'án', 3: 'án', 6: 'án', 8: 'án', 13: 'án', 16: 'án', 18: 'án', 20: 'án', 23: 'án', 26: 'án', 28: 'án', 30: 'án',
};
const onDay = (d: string) => `${d}-${ON_DAY[d] ?? 'én'}`;

/** `monthly:10` → „havonta 10-én", `quarterly:20` → „negyedévente 20-án"; anything unrecognised is shown as stored. */
export function recurrenceLabel(r: string | null): string {
  if (!r) return '—';
  const [kind, arg] = r.split(':');
  if (kind === 'monthly') return `havonta ${onDay(arg)}`;
  if (kind === 'quarterly') return `negyedévente ${onDay(arg)}`;
  if (kind === 'yearly') return `évente ${arg.replace('-', '.')}.`;
  if (kind === 'weekly') return `hetente ${WEEKDAY[arg] ?? arg}`;
  return r;
}

/** Today in the viewer's own calendar, as YYYY-MM-DD. */
export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export const isOverdue = (row: Pick<CaseRow, 'due_at' | 'status'>) =>
  !!row.due_at && ['open', 'waiting'].includes(row.status) && row.due_at < today();
