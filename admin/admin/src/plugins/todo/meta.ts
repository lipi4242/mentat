export const API = '/api/todo/v1';
export type Principal = { id: string; kind: string; handle: string; display_name: string; avatar: string | null; auth_email: string | null; agent_token_id: string | null; disabled_at: string | null };
export type Label = { id: string; name: string; color: string | null };
export type Task = { id: string; parent_id: string | null; title: string; description: string | null; status: 'open' | 'done' | 'dropped';
  position: string; rev: number; owner_id: string; assignee_id: string | null; assignee_note: string | null;
  due_date: string | null; due_time: string | null; planned_date: string | null; tz: string; repeat_rule: string | null;
  repeat_from: string; archived: number; progress: { done: number; total: number; percent: number } | null };
export type Comment = { id: string; body: string; display_name: string; avatar: string | null; handle?: string; kind?: 'human' | 'agent'; created_at: string };
export type Detail = Task & { children: Task[]; labels: Label[]; comments: Comment[] };
export type TreeTask = Task & { children?: TreeTask[] };
export const statuses = { open: 'Nyitott', done: 'Kész', dropped: 'Elengedve' };
export function today(tz = 'Europe/Budapest') {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  return ['year','month','day'].map(k => parts.find(p => p.type === k)!.value).join('-');
}
export function dateLabel(task: Task) {
  if (!task.due_date) return '';
  const now = today(task.tz), date = new Date(`${task.due_date}T12:00:00Z`);
  const days = Math.round((Date.parse(task.due_date) - Date.parse(now)) / 86400000);
  const label = days === 0 ? 'ma' : days === 1 ? 'holnap' : days > 1 && days <= 6
    ? new Intl.DateTimeFormat('hu', { weekday: 'long', timeZone: 'UTC' }).format(date)
    : new Intl.DateTimeFormat('hu', { month: 'short', day: 'numeric', timeZone: 'UTC',
      ...(now.slice(0, 4) !== task.due_date.slice(0, 4) ? { year: 'numeric' as const } : {}) }).format(date);
  return `${label}${task.due_time ? ` ${task.due_time}` : ''}`;
}
export function tree(rows: Task[], upcoming: boolean, justDone = new Set<string>(), older = false): TreeTask[] {
  const sorted = [...rows].sort((a, b) => a.position < b.position ? -1 : a.position > b.position ? 1 : a.id.localeCompare(b.id));
  const map = new Map(sorted.map(r => [r.id, { ...r, children: undefined } as TreeTask]));
  const keep = new Set<string>(), children = new Map<string, Task[]>();
  for (const row of rows) if (row.parent_id) children.set(row.parent_id, [...(children.get(row.parent_id) ?? []), row]);
  const allowed = (row: Task) => {
    const seen = new Set<string>(); let current: Task | undefined = row;
    while (current && !seen.has(current.id)) {
      if (current.archived || current.status === 'dropped') return false;
      seen.add(current.id); current = map.get(current.parent_id ?? '');
    }
    return true;
  };
  const descendants = (root: Task) => {
    const queue = [root]; const seen = new Set<string>();
    for (let i = 0; i < queue.length; i++) {
      const row = queue[i];
      if (seen.has(row.id) || row.archived || row.status === 'dropped') continue;
      seen.add(row.id); keep.add(row.id); queue.push(...(children.get(row.id) ?? []));
    }
  };
  for (const row of rows) {
    const start = today(row.tz), end = new Date(Date.parse(start) + 7 * 86400000).toISOString().slice(0, 10);
    const past = !!row.due_date && row.due_date < start;
    const matches = older ? past && !row.repeat_rule : !row.due_date || row.due_date <= end && (!past || !!row.repeat_rule);
    if (upcoming && (!allowed(row) || (!justDone.has(row.id) && (row.status !== 'open' || !matches)))) continue;
    if (upcoming) descendants(row);
    let id: string | null = row.id;
    const seen = new Set<string>();
    while (id && !seen.has(id)) { seen.add(id); keep.add(id); id = map.get(id)?.parent_id ?? null; }
  }
  const roots: TreeTask[] = [];
  for (const row of map.values()) {
    if (!keep.has(row.id)) continue;
    const parent = row.parent_id && map.get(row.parent_id);
    if (parent && keep.has(parent.id) && parent.id !== row.id) (parent.children ??= []).push(row); else roots.push(row);
  }
  return roots;
}
export function flatten(rows: TreeTask[]): TreeTask[] {
  const result: TreeTask[] = [], queue = [...rows];
  for (let i = 0; i < queue.length; i++) { result.push(queue[i]); queue.push(...(queue[i].children ?? [])); }
  return result;
}
export function possibleParents(rows: Task[], id: string) {
  const forbidden = new Set([id]);
  let changed = true;
  while (changed) { changed = false; for (const r of rows) if (r.parent_id && forbidden.has(r.parent_id) && !forbidden.has(r.id)) { forbidden.add(r.id); changed = true; } }
  return rows.filter(r => !forbidden.has(r.id));
}
export function relativeTime(value: string) {
  const minutes = Math.round((Date.parse(value) - Date.now()) / 60000);
  const rtf = new Intl.RelativeTimeFormat('hu', { numeric: 'auto' });
  if (Math.abs(minutes) < 1) return 'most';
  if (Math.abs(minutes) < 60) return rtf.format(minutes, 'minute');
  if (Math.abs(minutes) < 1440) return rtf.format(Math.round(minutes / 60), 'hour');
  return rtf.format(Math.round(minutes / 1440), 'day');
}
