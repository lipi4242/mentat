import { useState } from 'react';
import { Button, Input, Typography } from 'antd';
import { AlignLeftOutlined } from '@ant-design/icons';
export function EditableNote({ value, label, save }: { value: string | null; label: string; save: (value: string | null) => Promise<unknown> }) {
  const [draft, setDraft] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const submit = async () => {
    if (draft === null || busy) return;
    setBusy(true);
    try { if (draft !== (value ?? '')) await save(draft || null); setDraft(null); }
    catch { /* Keep the draft; the shared writer explains the failure. */ }
    finally { setBusy(false); }
  };
  return draft !== null ? <Input.TextArea autoFocus aria-label={label} autoSize={{ minRows: 2 }} readOnly={busy}
    value={draft} onChange={e => setDraft(e.target.value)} onBlur={() => void submit()} />
    : value ? <Typography.Paragraph className="todo-note" editable={{ tooltip: 'Szerkesztés', onStart: () => setDraft(value) }}
      onClick={() => setDraft(value)}>{value}</Typography.Paragraph>
      : <Button type="text" icon={<AlignLeftOutlined />} onClick={() => setDraft('')}>{label}</Button>;
}
