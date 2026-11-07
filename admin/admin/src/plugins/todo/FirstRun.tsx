import { useRef, useState } from 'react';
import { Alert, Button } from 'antd';
import { UserAddOutlined } from '@ant-design/icons';
import { authClient } from '../../lib/authClient';
import { apiSend } from '../../lib/api';
import { API } from './meta';
export function FirstRun({ onCreated }: { onCreated: () => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const key = useRef(crypto.randomUUID());
  const create = async () => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const session = await authClient.getSession();
      const email = session.data?.user.email?.trim().toLowerCase();
      if (!email) throw new Error('Jelentkezz be újra.');
      const name = email.split('@')[0];
      const handle = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9_]/g, '_').slice(0, 64) || 'en';
      await apiSend('POST', `${API}/principals`, { kind: 'human', auth_email: email, display_name: name, handle, idem_key: key.current });
      onCreated();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return <div className="todo-empty">
    <UserAddOutlined style={{ fontSize: 40, color: '#c9d0d4' }} />
    <p>Még nem ismerlek. Csináljak neked egy helyet?</p>
    {error && <Alert type="info" message={error} />}
    <Button loading={busy} onClick={create}>Létrehozlak</Button>
  </div>;
}
