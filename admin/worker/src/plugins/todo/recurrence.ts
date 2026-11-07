// Reuse cases' date validation and clamping; unlike cases, never enumerate backlog.
import { isIsoDate, nth, parseRecurrence } from '../cases/recurrence';
export { isIsoDate } from '../cases/recurrence';
const DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const DAY = 86400000;
const stamp = (s: string) => Date.parse(`${s}T00:00:00Z`);
const iso = (n: number) => new Date(n).toISOString().slice(0, 10);
export function todayIn(tz: string, now = new Date()): string {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const get = (type: string) => p.find(v => v.type === type)!.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}
export function validRule(rule: unknown): rule is string {
  if (typeof rule !== 'string') return false;
  if (['daily', 'weekdays', 'monthly:last'].includes(rule)) return true;
  const n = /^every:([1-9]\d*):(days|weeks|months)$/.exec(rule);
  if (n) return Number(n[1]) <= 3660;
  if (/^monthly:[1-5]:(sun|mon|tue|wed|thu|fri|sat)$/.test(rule)) return true;
  if (/^weekly:(sun|mon|tue|wed|thu|fri|sat)(,(sun|mon|tue|wed|thu|fri|sat))*$/.test(rule)) return true;
  return /^(monthly|yearly):/.test(rule) && !!parseRecurrence(rule);
}
export function nextDate(rule: string, due: string, today: string, from = 'schedule'): string {
  if (!validRule(rule) || !isIsoDate(due) || !isIsoDate(today)) throw new Error('invalid recurrence');
  const base = from === 'completion' ? today : due;
  const after = from === 'completion' ? today : (due > today ? due : today);
  const months = /^every:(\d+):months$/.exec(rule);
  if (months) {
    const step = Number(months[1]), [by, bm] = base.split('-').map(Number);
    const [ay, am] = after.split('-').map(Number), day = Number(due.slice(8));
    let count = Math.max(1, Math.floor(((ay - by) * 12 + am - bm) / step));
    // Anchor every candidate to due_date's day; a clamp must not drift the day
    // while skipping missed occurrences. Completion changes the month anchor.
    for (;; count++) {
      const first = new Date(Date.UTC(by, bm - 1 + count * step, 1));
      const y = first.getUTCFullYear(), m = first.getUTCMonth();
      if (y > 9999) throw new Error('recurrence outside supported calendar');
      const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
      const candidate = iso(Date.UTC(y, m, Math.min(day, last)));
      if (candidate > after) return candidate;
    }
  }
  const interval = /^every:(\d+):(days|weeks)$/.exec(rule);
  if (rule === 'daily' || interval) {
    const step = interval ? Number(interval[1]) * (interval[2] === 'weeks' ? 7 : 1) : 1;
    return iso(stamp(base) + (Math.floor((stamp(after) - stamp(base)) / DAY / step) + 1) * step * DAY);
  }
  if (rule === 'weekdays' || rule.startsWith('weekly:')) {
    const days = rule === 'weekdays' ? DAYS.slice(1, 6) : rule.slice(7).split(',');
    for (let i = 1; i <= 7; i++) {
      const n = stamp(after) + i * DAY;
      if (days.includes(DAYS[new Date(n).getUTCDay()])) return iso(n);
    }
  }
  const r = parseRecurrence(rule);
  const [y, m] = after.split('-').map(Number);
  if (r?.kind === 'yearly') {
    const candidate = nth(`${y}-01-01`, r, 0);
    return candidate > after ? candidate : nth(`${y}-01-01`, r, 1);
  }
  const ordinal = /^monthly:([1-5]):(\w+)$/.exec(rule);
  for (let i = 0; i < 24; i++) {
    const first = new Date(Date.UTC(y, m - 1 + i, 1));
    const yy = first.getUTCFullYear(), mm = first.getUTCMonth();
    const last = new Date(Date.UTC(yy, mm + 1, 0)).getUTCDate();
    const day = ordinal ? 1 + (DAYS.indexOf(ordinal[2]) - first.getUTCDay() + 7) % 7 + (Number(ordinal[1]) - 1) * 7
      : rule === 'monthly:last' ? last : Math.min(Number(rule.split(':')[1]), last);
    if (day > last) continue;
    const candidate = iso(Date.UTC(yy, mm, day));
    if (candidate > after) return candidate;
  }
  throw new Error('recurrence outside supported calendar');
}
