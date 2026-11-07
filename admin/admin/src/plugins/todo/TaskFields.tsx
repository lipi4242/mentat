import { useState } from 'react';
import { CalendarOutlined, SyncOutlined, UserOutlined } from '@ant-design/icons';
import { Input, Select, Space } from 'antd';
import { type Detail, type Principal } from './meta';
import { DueChip } from './DueChip';
import { FieldPopover } from './FieldPopover';
import { RepeatPicker } from './RepeatPicker';
import { repeatLabel } from './repeat';
import type { WriteTask } from './useTaskWrites';
type Draft = Partial<Pick<Detail, 'due_date' | 'due_time' | 'tz' | 'owner_id' | 'assignee_id' | 'repeat_rule' | 'repeat_from'>>;
export function TaskFields({ row, principals, write }: { row: Detail; principals: Principal[]; write: WriteTask }) {
  // Store only edits. Comment/revision reloads update untouched fields without
  // remounting this editor or overwriting anything the user has typed.
  const [draft, setDraft] = useState<Draft>({});
  const value = { ...row, ...draft };
  const change = (set: Draft) => setDraft(prev => ({ ...prev, ...set }));
  const save = async (keys: (keyof Draft)[]) => {
    const set = Object.fromEntries(keys.filter(k => k in draft && draft[k] !== row[k]).map(k => [k, draft[k]]));
    if (Object.keys(set).length) await write(row, set);
    setDraft(prev => {
      const next = { ...prev };
      for (const k of keys) if (prev[k] === draft[k]) delete next[k];
      return next;
    });
  };
  const options = principals.filter(p => !p.disabled_at || [value.owner_id, value.assignee_id].includes(p.id))
    .map(p => ({ value: p.id, label: p.display_name, disabled: !!p.disabled_at }));
  return <>
    <FieldPopover label="Határidő" icon={<CalendarOutlined />} value={value.due_date ? <DueChip row={value} /> : undefined}
      onClose={() => save(['due_date', 'due_time', 'tz'])}>
      <Space direction="vertical">
        <Input aria-label="Határidő napja" type="date" value={value.due_date ?? ''}
          onChange={e => change({ due_date: e.target.value || null, ...(!e.target.value ? { due_time: null } : {}) })} />
        <Input aria-label="Időpont" type="time" disabled={!value.due_date} value={value.due_time ?? ''} onChange={e => change({ due_time: e.target.value || null })} />
        <details><summary>Időzóna</summary><Input aria-label="Időzóna" value={value.tz} onChange={e => change({ tz: e.target.value })} /></details>
      </Space>
    </FieldPopover>
    <FieldPopover label="Résztvevők" icon={<UserOutlined />} value={<><UserOutlined /> {principals.find(p => p.id === value.owner_id)?.display_name}</>}
      onClose={() => save(['owner_id', 'assignee_id'])}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Select aria-label="Tulajdonos" value={value.owner_id} options={options} onChange={owner_id => change({ owner_id })} />
        <Select aria-label="Kiosztott" placeholder="Nálad a labda" allowClear value={value.assignee_id} options={options}
          onChange={assignee_id => change({ assignee_id: assignee_id ?? null })} />
      </Space>
    </FieldPopover>
    <FieldPopover label="Ismétlődés" icon={<SyncOutlined />} value={value.repeat_rule ? <><SyncOutlined /> {repeatLabel(value.repeat_rule)}</> : undefined}
      onClose={() => save(['repeat_rule', 'repeat_from', 'due_date'])}>
      <RepeatPicker value={value} onChange={change} />
    </FieldPopover>
  </>;
}
