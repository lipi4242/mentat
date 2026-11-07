import { describe, expect, it } from 'vitest';
import { buildRule, parseRule, describe as describeRule } from './repeat';
import { RepeatPicker } from './RepeatPicker';
import { show, click, task, tick } from './testkit';
import { today } from './meta';
describe('repeat rules', () => {
  it.each([null, 'daily', 'weekdays', 'weekly:mon,wed,fri', 'monthly:15', 'monthly:last', 'monthly:2:tue',
    'monthly:5:mon', 'yearly:02-29', 'yearly:03-14', 'every:3:days', 'every:2:weeks', 'every:3:months', 'every:3660:months'])('round-trips %s', rule => {
    const model = parseRule(rule);
    expect(model).not.toBeNull();
    expect(buildRule(model!)).toBe(rule);
    expect(parseRule(buildRule(model!))).toEqual(model);
  });
  it.each(['unknown', 'yearly:02-30', 'every:0:months', 'every:3661:months', 'monthly:6:tue'])('preserves an unrecognized %s', rule => {
    expect(parseRule(rule)).toBeNull();
  });
  it('describes month intervals in Hungarian', () => {
    expect(describeRule(parseRule('every:3:months')!)).toBe('3 havonta');
  });
  it('sets a missing start date when selecting recurrence', async () => {
    const edits: unknown[] = [];
    await show('/repeat', [['repeat', <RepeatPicker value={task} onChange={set => edits.push(set)} />]]);
    const input = document.querySelector('input[aria-label="Ismétlődés"]')!;
    input.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    await tick(50);
    const option = [...document.querySelectorAll('.ant-select-item-option')].find(e => e.textContent?.includes('Időközönként'));
    await click(option);
    expect(edits[0]).toEqual({ repeat_rule: 'every:3:days', due_date: today(task.tz) });
  });
  it('selects N havonta with the existing due date as anchor', async () => {
    const edits: unknown[] = [];
    await show('/repeat', [['repeat', <RepeatPicker value={{ ...task, due_date: '2026-01-31', repeat_rule: 'every:3:days' }} onChange={set => edits.push(set)} />]]);
    document.querySelector('input[aria-label="Időegység"]')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    await tick(50);
    await click([...document.querySelectorAll('.ant-select-item-option')].find(e => e.textContent === 'havonta'));
    expect(edits[0]).toEqual({ repeat_rule: 'every:3:months' });
  });
  it('leaves unknown rules read-only and untouched', async () => {
    const edits: unknown[] = [];
    await show('/repeat', [['repeat', <RepeatPicker value={{ ...task, repeat_rule: 'legacy:custom' }} onChange={set => edits.push(set)} />]]);
    const input = document.querySelector('input[aria-label="Egyedi szabály"]') as HTMLInputElement;
    expect(input.readOnly).toBe(true); expect(input.value).toBe('legacy:custom');
    expect(edits).toEqual([]);
  });
  it('renders a month interval', async () => {
    const { container } = await show('/repeat', [['repeat', <RepeatPicker value={{ ...task, repeat_rule: 'every:3:months' }} onChange={() => {}} />]]);
    expect(container.textContent).toContain('havonta');
  });
});
