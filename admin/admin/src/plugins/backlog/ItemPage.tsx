import { Link, useParams } from 'react-router-dom';
import { Alert, Skeleton, Tag, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { API, prefixOf, stageLabel, type ItemDetail, type Me, type Principal } from './meta';
import { ItemActions } from './ItemActions';
import { ItemDetails } from './ItemDetails';
export function ItemPage() {
  const { id: ref = "" } = useParams();
  const item = useApi<ItemDetail>(`${API}/items/${encodeURIComponent(ref)}`);
  const me = useApi<Me>(`${API}/me`), principals = useApi<Principal[]>(`${API}/principals`);
  const row = item.data, err = item.error || me.error || principals.error;
  const who = (id: string | null) => principals.data?.find(p => p.id === id)?.display_name;
  return <main className="todo-page bl-page">
    <Typography.Text type="secondary"><Link to="/labda">Kinél a labda</Link>{row && <> · <Link to={`/projekt/${prefixOf(row.key)}`}>{prefixOf(row.key)}</Link></>}</Typography.Text>
    {err && <Alert type="info" message={err.message} />}
    {!row ? <Skeleton active /> : <>
      <header className="bl-title"><Typography.Title level={4}>{row.key} · {row.title}</Typography.Title>
        <Tag>{stageLabel[row.stage]}</Tag></header>
      <Typography.Paragraph type="secondary">Nála a labda: {who(row.assignee_id ?? row.owner_id) ?? '—'}
        {row.dev_id && <> · Fejlesztő: {who(row.dev_id)}</>}</Typography.Paragraph>
      {me.data && <ItemActions item={row} me={me.data} principals={principals.data ?? []} reload={item.reload} />}
      <ItemDetails item={row} />
    </>}
  </main>;
}
