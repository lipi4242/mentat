import { useState } from 'react';
import { Alert, Modal, Select } from 'antd';
import { apiSend, ApiError } from '../../lib/api';
import { API, possibleParents, type Task } from './meta';
export function MoveTask({ row, rows, onClose, onSaved }: { row: Task; rows: Task[]; onClose: () => void; onSaved: () => void }) {
  const [parent, setParent] = useState(row.parent_id ?? ''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [rev, setRev] = useState(row.rev);
  const save = async () => {
    setBusy(true); setError('');
    try { await apiSend('POST', `${API}/tasks/${row.id}/move`, { parent_id: parent || null, expected_rev: rev }); onSaved(); onClose(); }
    catch (e) {
      if (e instanceof ApiError && e.statusCode === 409) {
        const current = (e.body as { current?: Task })?.current;
        if (current) setRev(current.rev);
        setError('Közben valaki módosította, frissítettem.'); onSaved();
      }
      else setError((e as Error).message);
    } finally { setBusy(false); }
  };
  return <Modal open title="Áthelyezés ide…" okText="Áthelyezés" cancelText="Mégse" onCancel={onClose} onOk={save} confirmLoading={busy}>
    {error && <Alert type="info" message={error} />}
    <Select aria-label="Új szülő" style={{ width: '100%' }} showSearch optionFilterProp="label" value={parent} onChange={setParent}
      options={[{ value: '', label: 'Gyökérszint' }, ...possibleParents(rows, row.id).map(r => ({ value: r.id, label: r.title }))]} />
  </Modal>;
}
