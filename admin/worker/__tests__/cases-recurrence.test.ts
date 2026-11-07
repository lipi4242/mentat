// The anchored-recurrence rules of the cases plugin. The brain's markdown
// `case` template and the engine's concern package compute the same series,
// so these cases are the shared contract: a short month takes its last day.
import { describe, it, expect } from 'vitest';
import {
  parseRecurrence,
  nth,
  anchorProblem,
  firstOpenAfter,
  seriesBetween,
  isIsoDate,
} from '../src/plugins/cases/recurrence';

const r = (s: string) => {
  const p = parseRecurrence(s);
  if (!p) throw new Error(`unparsed: ${s}`);
  return p;
};
const first = (anchor: string, rec: string, n: number) => Array.from({ length: n }, (_, k) => nth(anchor, r(rec), k));

describe('parseRecurrence', () => {
  it.each(['monthly:1', 'monthly:10', 'monthly:31', 'yearly:05-20', 'yearly:02-29', 'weekly:mon', 'weekly:sun'])(
    'accepts %s',
    (s) => expect(parseRecurrence(s)).not.toBeNull(),
  );
  it.each(['monthly:0', 'monthly:32', 'monthly:1x', 'yearly:13-01', 'yearly:02-30', 'yearly:5-20', 'weekly:xyz', 'daily:1', '', 'monthly'])(
    'rejects %j',
    (s) => expect(parseRecurrence(s)).toBeNull(),
  );
});

describe('nth occurrence', () => {
  it('monthly on the 10th', () => {
    expect(first('2026-10-10', 'monthly:10', 4)).toEqual(['2026-10-10', '2026-11-10', '2026-12-10', '2027-01-10']);
  });

  it('monthly:31 falls on the last day of a short month, and comes back to the 31st', () => {
    expect(first('2027-01-31', 'monthly:31', 4)).toEqual(['2027-01-31', '2027-02-28', '2027-03-31', '2027-04-30']);
    expect(nth('2028-01-31', r('monthly:31'), 1)).toBe('2028-02-29');
  });

  it('yearly:02-29 is the 28th outside leap years', () => {
    expect(first('2028-02-29', 'yearly:02-29', 5)).toEqual(['2028-02-29', '2029-02-28', '2030-02-28', '2031-02-28', '2032-02-29']);
  });

  it('weekly steps seven days across a month end', () => {
    expect(first('2026-10-26', 'weekly:mon', 2)).toEqual(['2026-10-26', '2026-11-02']);
  });
});

describe('anchorProblem', () => {
  it('accepts an anchor on the series', () => {
    expect(anchorProblem('2026-10-10', r('monthly:10'))).toBeNull();
    expect(anchorProblem('2027-02-28', r('monthly:31'))).toBeNull();
    expect(anchorProblem('2026-10-12', r('weekly:mon'))).toBeNull();
  });
  it('names an anchor that is not a date of the series', () => {
    expect(anchorProblem('2026-10-12', r('monthly:10'))).toMatch(/2026-10-10/);
    expect(anchorProblem('2026-10-10', r('weekly:mon'))).toMatch(/mon/);
    expect(anchorProblem('2026-05-21', r('yearly:05-20'))).toMatch(/05-20/);
  });
});

describe('firstOpenAfter / seriesBetween', () => {
  it('starts at the anchor when nothing is closed', () => {
    expect(firstOpenAfter('2026-10-10', r('monthly:10'), null)).toBe('2026-10-10');
  });
  it('is the first date after the last closed one', () => {
    expect(firstOpenAfter('2026-10-10', r('monthly:10'), '2026-10-10')).toBe('2026-11-10');
    expect(firstOpenAfter('2027-01-31', r('monthly:31'), '2027-01-31')).toBe('2027-02-28');
  });
  it('lists every open date in a window, capped', () => {
    expect(seriesBetween('2026-08-10', r('monthly:10'), '2026-09-01', '2026-11-10', 10)).toEqual([
      '2026-09-10',
      '2026-10-10',
      '2026-11-10',
    ]);
    expect(seriesBetween('2026-10-12', r('weekly:mon'), '2026-10-12', '2030-01-01', 3)).toHaveLength(3);
    expect(seriesBetween('2026-10-10', r('monthly:10'), '2026-10-11', '2026-11-09', 10)).toEqual([]);
  });
});

describe('isIsoDate', () => {
  it('accepts only real calendar dates', () => {
    expect(isIsoDate('2026-02-28')).toBe(true);
    expect(isIsoDate('2026-02-29')).toBe(false);
    expect(isIsoDate('2026-2-1')).toBe(false);
    expect(isIsoDate('2026-10-10T00:00:00Z')).toBe(false);
    expect(isIsoDate(20261010)).toBe(false);
  });
});

// quarterly:<day> — the phase is the anchor's month (anchor 2026-01-20 →
// January, April, July, October), the short-month rule is monthly's.
describe('quarterly', () => {
  it.each(['quarterly:1', 'quarterly:20', 'quarterly:31'])('accepts %s', (s) => expect(parseRecurrence(s)).not.toBeNull());
  it.each(['quarterly:0', 'quarterly:32', 'quarterly', 'quarterly:q1'])('rejects %j', (s) => expect(parseRecurrence(s)).toBeNull());

  it('steps three months from the anchor and rolls over the year', () => {
    expect(first('2026-01-20', 'quarterly:20', 5)).toEqual(['2026-01-20', '2026-04-20', '2026-07-20', '2026-10-20', '2027-01-20']);
    expect(first('2026-11-20', 'quarterly:20', 3)).toEqual(['2026-11-20', '2027-02-20', '2027-05-20']);
  });

  it('a 31st anchor falls on the last day of February and April, and comes back', () => {
    expect(first('2026-11-30', 'quarterly:31', 4)).toEqual(['2026-11-30', '2027-02-28', '2027-05-31', '2027-08-31']);
    expect(first('2027-01-31', 'quarterly:31', 3)).toEqual(['2027-01-31', '2027-04-30', '2027-07-31']);
    expect(nth('2027-11-30', r('quarterly:31'), 1)).toBe('2028-02-29');
  });

  it('names an anchor off the day, and takes any month as the phase', () => {
    expect(anchorProblem('2026-02-20', r('quarterly:20'))).toBeNull();
    expect(anchorProblem('2026-01-21', r('quarterly:20'))).toMatch(/2026-01-20/);
    expect(anchorProblem('2026-11-30', r('quarterly:31'))).toBeNull();
  });

  it('the next open date after a closed quarter', () => {
    expect(firstOpenAfter('2026-01-20', r('quarterly:20'), '2026-01-20')).toBe('2026-04-20');
    expect(seriesBetween('2026-01-20', r('quarterly:20'), '2026-03-01', '2026-12-31', 10)).toEqual(['2026-04-20', '2026-07-20', '2026-10-20']);
  });
});
