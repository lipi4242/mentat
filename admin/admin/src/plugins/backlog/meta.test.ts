import { describe, expect, it } from 'vitest';
import { between, verbsFor, type Me } from './meta';
const human: Me = { id: 'h', kind: 'human', handle: 'krisz' }, dev: Me = { id: 'd', kind: 'agent', handle: 'dev' };
const item = (stage: 'draft' | 'issued' | 'taken' | 'review' | 'done' | 'hold' | 'dropped') => ({ stage, owner_id: 'h', dev_id: 'd' });
describe('verbsFor', () => {
  it('shows only what stage and actor allow', () => {
    expect(verbsFor(item('draft'), human)).toEqual(['issue', 'hold', 'drop']);
    expect(verbsFor(item('review'), human)).toContain('accept');
    expect(verbsFor(item('review'), dev)).toEqual([]);
    expect(verbsFor(item('issued'), dev)).toEqual(['take', 'handback']);
    expect(verbsFor(item('hold'), human)).toEqual(['resume', 'drop']);
  });
  it('offers nothing from terminal stages', () => {
    expect(verbsFor(item('done'), human)).toEqual([]);
    expect(verbsFor(item('dropped'), human)).toEqual([]);
  });
});
describe('between', () => {
  it('stays strictly between neighbours', () => {
    for (const [a, b] of [['', 'U'], ['U', 'V'], ['U', 'W'], ['Uz', 'V'], ['a', 'a~']]) {
      const m = between(a, b)!; expect(m && m > a && m < b, `${a}|${b}|${m}`).toBe(true);
    }
  });
  it('says no when there is no room', () => expect(between('U', 'U!')).toBeNull());
});
