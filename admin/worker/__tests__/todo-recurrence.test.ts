import { describe, expect, it } from 'vitest';
import { nextDate, validRule, todayIn } from '../src/plugins/todo/recurrence';

describe('todo recurrence skips backlog and retains calendar intent', () => {
  it.each([
    ['every:1:months', '2026-01-31', '2026-01-31', 'schedule', '2026-02-28'],
    ['every:1:months', '2024-01-31', '2024-01-31', 'schedule', '2024-02-29'],
    ['every:2:months', '2026-01-31', '2026-03-31', 'schedule', '2026-05-31'],
    ['every:2:months', '2026-01-31', '2026-10-27', 'schedule', '2026-11-30'],
    ['every:1:months', '2026-01-31', '2026-02-28', 'schedule', '2026-03-31'],
    ['every:3:months', '2026-11-30', '2026-11-30', 'schedule', '2027-02-28'],
    ['every:2:months', '2026-01-31', '2026-10-02', 'completion', '2026-12-31'],
    ['every:1:months', '2026-01-31', '2026-01-02', 'schedule', '2026-02-28'],
    ['every:1:months', '2000-01-31', '2099-10-31', 'schedule', '2099-11-30'],
    ['daily', '2026-01-01', '2026-10-27', 'schedule', '2026-10-28'],
    ['weekdays', '2026-10-23', '2026-10-23', 'schedule', '2026-10-26'],
    ['weekly:mon,wed,fri', '2026-10-26', '2026-10-27', 'schedule', '2026-10-28'],
    ['every:3:days', '2026-10-01', '2026-10-27', 'schedule', '2026-10-28'],
    ['every:2:weeks', '2026-10-01', '2026-10-27', 'schedule', '2026-10-29'],
    ['monthly:last', '2026-01-31', '2026-02-01', 'schedule', '2026-02-28'],
    ['monthly:31', '2026-02-28', '2026-02-28', 'schedule', '2026-03-31'],
    ['monthly:2:tue', '2026-01-13', '2026-10-27', 'schedule', '2026-11-10'],
    ['monthly:5:mon', '2026-03-30', '2026-04-01', 'schedule', '2026-06-29'],
    ['yearly:02-29', '2024-02-29', '2026-01-01', 'schedule', '2026-02-28'],
    ['yearly:03-14', '2026-03-14', '2026-10-27', 'schedule', '2027-03-14'],
    ['every:3:days', '2026-10-01', '2026-10-27', 'completion', '2026-10-30'],
    ['monthly:15', '2026-01-15', '2026-10-27', 'completion', '2026-11-15'],
    ['daily', '2000-01-01', '2099-10-27', 'schedule', '2099-10-28'],
    ['daily', '2026-11-01', '2026-10-27', 'schedule', '2026-11-02'],
  ])('%s from %s after %s (%s)', (rule, due, today, from, want) => {
    expect(nextDate(rule, due, today, from)).toBe(want);
  });
  it.each(['every:0:months', 'every:3661:months', 'every:1.5:months', 'every:-1:months', 'every:0:days', 'every:99999:weeks', 'monthly:6:mon', 'weekly:foo', 'yearly:02-30', 'daily '])('rejects %s', rule => {
    expect(validRule(rule)).toBe(false);
  });
  it('uses the task timezone at midnight', () => {
    expect(todayIn('Europe/Budapest', new Date('2026-10-27T23:30:00Z'))).toBe('2026-10-28');
  });
});
