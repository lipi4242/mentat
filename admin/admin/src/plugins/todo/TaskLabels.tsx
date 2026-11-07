import { useState } from 'react';
import { Select } from 'antd';
import { TagOutlined } from '@ant-design/icons';
import { type Detail, type Label } from './meta';
import { FieldPopover } from './FieldPopover';
import type { WriteTask } from './useTaskWrites';
export function TaskLabels({ row, labels, write }: { row: Detail; labels: Label[]; write: WriteTask }) {
  const [draft, setDraft] = useState<string[] | null>(null);
  const ids = draft ?? row.labels.map(l => l.id);
  const save = async () => {
    if (draft && [...ids].sort().join('|') !== row.labels.map(l => l.id).sort().join('|')) {
      await write(row, { label_ids: ids }, 'labels');
    }
    setDraft(null);
  };
  return <FieldPopover label="Címkék" icon={<TagOutlined />} onClose={save}
    value={ids.length ? <><TagOutlined /> {labels.filter(l => ids.includes(l.id)).map(l => l.name).join(', ')}</> : undefined}>
    <Select aria-label="Címkék kiválasztása" mode="multiple" value={ids} onChange={setDraft} style={{ width: '100%' }}
      options={labels.map(l => ({ value: l.id, label: l.name }))} />
  </FieldPopover>;
}
