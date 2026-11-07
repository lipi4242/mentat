import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Alert, Button, Modal, Select, Skeleton, Tag, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { apiSend, ApiError } from '../../lib/api';
import { API, between, stageLabel, type Item } from './meta';
export function ProjectPage() {
  const { id: prefix = "" } = useParams();
  const list = useApi<Item[]>(`${API}/items?project=${encodeURIComponent(prefix)}`);
  const [move, setMove] = useState<Item | null>(null), [target, setTarget] = useState<string>(), [error, setError] = useState('');
  const rows = [...(list.data ?? [])].filter(i => i.stage !== 'done' && i.stage !== 'dropped')
    .sort((a, b) => a.position < b.position ? -1 : a.position > b.position ? 1 : a.id.localeCompare(b.id));
  const close = () => { setMove(null); setTarget(undefined); };
  const save = async () => {
    const dest = rows.find(r => r.id === target); if (!move || !dest) return;
    const sibs = rows.filter(r => r.parent_id === move.parent_id && r.id !== move.id), at = sibs.indexOf(dest);
    const position = between(sibs[at - 1]?.position ?? '', dest.position);
    if (!position) { setError('Itt már nincs hely a beszúrásra — szólj, és újraszámoljuk a sorrendet.'); return; }
    try { await apiSend('POST', `${API}/tasks/${move.id}/move`, { parent_id: move.parent_id, position, expected_rev: move.rev }); setError(''); close(); }
    catch (e) { setError(e instanceof ApiError && e.statusCode === 409 ? 'Közben valaki módosította, frissítettem.' : (e as Error).message); close(); }
    list.reload();
  };
  const choices = move ? rows.filter(r => r.parent_id === move.parent_id && r.id !== move.id) : [];
  return <main className="todo-page bl-page">
    <Typography.Text type="secondary"><Link to="/projektek">Projektek</Link></Typography.Text>
    <Typography.Title level={4}>{prefix}</Typography.Title>
    {(error || list.error) && <Alert type="info" message={error || list.error?.message} />}
    {list.loading && !list.data ? <Skeleton active /> : !rows.length ? <Typography.Paragraph type="secondary">Itt most nincs nyitott tétel.</Typography.Paragraph>
      : <ol className="bl-ranked">{rows.map((r, n) => <li key={r.id} className="todo-row">
        <span className="bl-rank">{n + 1}.</span>
        <Link className="todo-row-title" to={`/tetel/${r.key}`}><b>{r.key}</b> {r.title}</Link>
        <Tag>{stageLabel[r.stage]}</Tag>
        {rows.length > 1 && <Button type="text" aria-label={`${r.key} mozgatása`} onClick={() => setMove(r)}>Mozgasd ez fölé…</Button>}
      </li>)}</ol>}
    {move && <Modal open title={`${move.key}: mozgasd ez fölé…`} okText="Áthelyezés" cancelText="Mégse" onCancel={close} onOk={save} okButtonProps={{ disabled: !target }}>
      <Select aria-label="Melyik fölé" style={{ width: '100%' }} placeholder="Melyik tétel fölé kerüljön?" value={target} onChange={setTarget}
        options={choices.map(r => ({ value: r.id, label: `${r.key} ${r.title}` }))} />
    </Modal>}
  </main>;
}
