import { Button, Input, InputNumber, Segmented, Select, Space, Typography } from 'antd';
import { CalendarOutlined, CheckOutlined } from '@ant-design/icons';
import { buildRule, days, dayNames, parseRule, type Rule } from './repeat';
import { today } from './meta';
type Value = { repeat_rule: string | null; repeat_from: string; due_date: string | null; tz: string };
export function RepeatPicker({ value, onChange }: { value: Value; onChange: (set: Partial<Value>) => void }) {
  const model = parseRule(value.repeat_rule);
  const change = (next: Rule) => onChange({ repeat_rule: buildRule(next),
    ...(next.kind !== 'none' && !value.due_date ? { due_date: today(value.tz) } : {}) });
  const defaults: Record<string, Rule> = { none: { kind: 'none' }, daily: { kind: 'daily' }, weekdays: { kind: 'weekdays' },
    weekly: { kind: 'weekly', days: ['mon'] }, monthly: { kind: 'monthly', mode: 'day', day: 15, nth: 2, weekday: 'tue' },
    yearly: { kind: 'yearly', month: 1, day: 1 }, every: { kind: 'every', n: 3, unit: 'days' } };
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Select aria-label="Ismétlődés" style={{ width: '100%' }} value={model?.kind ?? 'custom'} onChange={kind => { if (defaults[kind]) change(defaults[kind]); }}
      options={[['none', 'Nem ismétlődik'], ['daily', 'Minden nap'], ['weekdays', 'Munkanapokon'], ['weekly', 'Hetente'],
        ['monthly', 'Havonta'], ['yearly', 'Évente'], ['every', 'Időközönként'], ...(!model ? [['custom', 'Egyedi']] : [])].map(([value, label]) => ({ value, label }))} />
    {!model && <Input readOnly aria-label="Egyedi szabály" value={value.repeat_rule ?? ''} />}
    {model?.kind === 'weekly' && <Space size={4} wrap>{days.map((day, i) => <Button key={day} shape="circle" size="small"
      aria-label={dayNames[i]} aria-pressed={model.days.includes(day)} type={model.days.includes(day) ? 'primary' : 'default'}
      onClick={() => { const selected = model.days.includes(day) ? model.days.filter(d => d !== day) : [...model.days, day]; if (selected.length) change({ ...model, days: days.filter(d => selected.includes(d)) }); }}>
      {['H', 'K', 'Sz', 'Cs', 'P', 'Szo', 'V'][i]}</Button>)}</Space>}
    {model?.kind === 'monthly' && <>
      <Segmented<'day' | 'last' | 'nth'> value={model.mode} onChange={mode => change({ ...model, mode })} options={[
        { value: 'day', label: 'Napján' }, { value: 'last', label: 'Utolsó napon' }, { value: 'nth', label: 'N-edik napon' }]} />
      {model.mode === 'day' && <InputNumber aria-label="Hónap napja" min={1} max={31} precision={0} value={model.day} onChange={day => day && change({ ...model, day })} />}
      {model.mode === 'nth' && <Space><InputNumber aria-label="Hányadik" min={1} max={5} precision={0} value={model.nth} onChange={nth => nth && change({ ...model, nth })} />
        <Select aria-label="Hét napja" value={model.weekday} options={days.map((value, i) => ({ value, label: dayNames[i] }))} onChange={weekday => change({ ...model, weekday })} /></Space>}
    </>}
    {model?.kind === 'yearly' && <Space>
      <Select aria-label="Hónap" value={model.month} options={Array.from({ length: 12 }, (_, i) => ({ value: i + 1,
        label: new Intl.DateTimeFormat('hu', { month: 'long' }).format(new Date(2000, i, 1)) }))}
        onChange={month => change({ ...model, month, day: Math.min(model.day, new Date(2000, month, 0).getDate()) })} />
      <InputNumber aria-label="Nap" min={1} max={new Date(2000, model.month, 0).getDate()} precision={0} value={model.day} onChange={day => day && change({ ...model, day })} />
    </Space>}
    {model?.kind === 'every' && <Space><InputNumber aria-label="Gyakoriság" min={1} max={3660} precision={0} value={model.n} onChange={n => n && change({ ...model, n })} />
      <Select aria-label="Időegység" value={model.unit} options={[{ value: 'days', label: 'naponta' }, { value: 'weeks', label: 'hetente' }, { value: 'months', label: 'havonta' }]}
        onChange={unit => change({ ...model, unit })} /></Space>}
    {value.repeat_rule && <Segmented value={value.repeat_from} onChange={repeat_from => onChange({ repeat_from })} options={[
      { value: 'schedule', label: 'Naptár szerint', icon: <CalendarOutlined /> }, { value: 'completion', label: 'Pipálástól', icon: <CheckOutlined /> }]} />}
    {value.repeat_rule && value.due_date === today(value.tz) && <Typography.Text type="secondary">Kezdő nap: ma</Typography.Text>}
  </Space>;
}
