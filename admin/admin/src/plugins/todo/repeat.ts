export const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
export const dayNames = ['hétfőn', 'kedden', 'szerdán', 'csütörtökön', 'pénteken', 'szombaton', 'vasárnap'];
export type Rule = { kind: 'none' | 'daily' | 'weekdays' } | { kind: 'weekly'; days: string[] }
  | { kind: 'monthly'; mode: 'day' | 'last' | 'nth'; day: number; nth: number; weekday: string }
  | { kind: 'yearly'; month: number; day: number } | { kind: 'every'; n: number; unit: 'days' | 'weeks' | 'months' };
export function parseRule(text: string | null): Rule | null {
  if (!text) return { kind: 'none' };
  if (text === 'daily' || text === 'weekdays') return { kind: text };
  const interval = /^every:([1-9]\d*):(days|weeks|months)$/.exec(text);
  if (interval && Number(interval[1]) <= 3660) return { kind: 'every', n: Number(interval[1]), unit: interval[2] as 'days' | 'weeks' | 'months' };
  if (/^weekly:(mon|tue|wed|thu|fri|sat|sun)(,(mon|tue|wed|thu|fri|sat|sun))*$/.test(text)) return { kind: 'weekly', days: text.slice(7).split(',') };
  const monthly = /^monthly:(last|[1-9]|[12]\d|3[01])$/.exec(text), nth = /^monthly:([1-5]):(mon|tue|wed|thu|fri|sat|sun)$/.exec(text);
  if (monthly || nth) return { kind: 'monthly', mode: nth ? 'nth' : monthly![1] === 'last' ? 'last' : 'day',
    day: monthly && monthly[1] !== 'last' ? Number(monthly[1]) : 15, nth: nth ? Number(nth[1]) : 2, weekday: nth?.[2] ?? 'tue' };
  const yearly = /^yearly:(\d{2})-(\d{2})$/.exec(text);
  if (yearly) {
    const month = Number(yearly[1]), day = Number(yearly[2]);
    if (month >= 1 && month <= 12 && day >= 1 && day <= new Date(Date.UTC(2000, month, 0)).getUTCDate()) return { kind: 'yearly', month, day };
  }
  return null;
}
export function buildRule(model: Rule): string | null {
  switch (model.kind) {
    case 'none': return null;
    case 'daily': case 'weekdays': return model.kind;
    case 'weekly': return `weekly:${model.days.join(',')}`;
    case 'every': return `every:${model.n}:${model.unit}`;
    case 'monthly': return `monthly:${model.mode === 'last' ? 'last' : model.mode === 'day' ? model.day : `${model.nth}:${model.weekday}`}`;
    case 'yearly': return `yearly:${String(model.month).padStart(2, '0')}-${String(model.day).padStart(2, '0')}`;
  }
}
export function describe(model: Rule): string {
  switch (model.kind) {
    case 'none': return 'Nem ismétlődik';
    case 'daily': return 'Minden nap';
    case 'weekdays': return 'Munkanapokon';
    case 'weekly': return model.days.map(d => dayNames[days.indexOf(d)]).join(', ');
    case 'every': return `${model.n} ${model.unit === 'days' ? 'naponta' : model.unit === 'weeks' ? 'hetente' : 'havonta'}`;
    case 'monthly': return model.mode === 'last' ? 'A hónap utolsó napján' : model.mode === 'day' ? `Havonta, ${model.day}. napján` : `Havonta, ${model.nth}. ${dayNames[days.indexOf(model.weekday)]}`;
    case 'yearly': return `Évente, ${model.month}. hó ${model.day}. napján`;
  }
}
export const repeatLabel = (rule: string | null) => { const model = parseRule(rule); return model ? describe(model) : 'Egyedi'; };
