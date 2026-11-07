import { useRef, useState } from 'react';
import { Alert, Input, type InputRef } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { apiSend } from '../../lib/api';
import { API } from './meta';
export function QuickAdd({ parent, onSaved, autoFocus = false }: { parent: string | null; onSaved: () => void; autoFocus?: boolean }) {
  const [title, setTitle] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const key = useRef(crypto.randomUUID()), input = useRef<InputRef>(null);
  const save = async () => {
    if (!title.trim() || busy) return;
    setBusy(true); setError('');
    try {
      await apiSend('POST', `${API}/tasks`, { title: title.trim(), parent_id: parent, idem_key: key.current });
      key.current = crypto.randomUUID(); setTitle(''); onSaved(); input.current?.focus();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return <div className="todo-add">
    {error && <Alert type="info" message={error} />}
    <Input ref={input} aria-label={parent ? 'Részfeladat címe' : 'Feladat címe'} autoFocus={autoFocus} prefix={<PlusOutlined />}
      readOnly={busy} value={title} onChange={e => setTitle(e.target.value)} onPressEnter={e => { if (!e.nativeEvent.isComposing) void save(); }} placeholder={parent ? 'Új részfeladat…' : 'Új feladat…'} />
  </div>;
}
