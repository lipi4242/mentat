import { Link } from 'react-router-dom';
import { Alert, Avatar, Skeleton, Tag, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { API, stageLabel, type Item, type Principal } from './meta';
type Todo = { id: string; title: string; kind?: 'todo' | 'case'; status: string; archived: number; owner_id: string; assignee_id: string | null };
type Entry = { id: string; title: string; to: string; tag: string; extra?: string; holder: string };
/** Everything somebody holds the ball on, from all three kinds, grouped by person. No dates, no "overdue". */
export function BallPage() {
  const tasks = useApi<Todo[]>(`${API}/tasks`), items = useApi<Item[]>(`${API}/items`), people = useApi<Principal[]>(`${API}/principals`);
  const entries: Entry[] = [
    ...(tasks.data ?? []).filter(t => t.status === 'open' && !t.archived).map(t => ({ id: t.id, title: t.title, to: `/feladatok/${t.id}`,
      tag: t.kind === 'case' ? 'Ügy' : 'Feladat', holder: t.assignee_id ?? t.owner_id })),
    ...(items.data ?? []).filter(i => i.stage !== 'done' && i.stage !== 'dropped').map(i => ({ id: i.id, title: `${i.key} ${i.title}`,
      to: `/tetel/${i.key}`, tag: 'Tétel', extra: stageLabel[i.stage], holder: i.assignee_id ?? i.owner_id })),
  ];
  const err = tasks.error || items.error || people.error, loading = (tasks.loading || items.loading || people.loading) && !people.data;
  return <main className="todo-page bl-page">
    <header className="todo-heading"><Typography.Title level={4}>Kinél a labda</Typography.Title><Link to="/projektek">Projektek</Link></header>
    {err && <Alert type="info" message={err.message} />}
    {loading ? <Skeleton active /> : !entries.length ? <Typography.Paragraph type="secondary">Most nincs nyitott tétel — kényelmesen hátradőlhetsz.</Typography.Paragraph>
      : (people.data ?? []).map(p => ({ p, rows: entries.filter(e => e.holder === p.id) })).filter(g => g.rows.length).map(({ p, rows }) =>
        <section key={p.id} className="bl-person" aria-label={p.display_name}>
          <Typography.Title level={5}><Avatar size={24} src={p.avatar}>{p.display_name.slice(0, 1)}</Avatar> {p.display_name} <Typography.Text type="secondary">({rows.length})</Typography.Text></Typography.Title>
          {rows.map(e => <div key={e.id} className="todo-row"><Link className="todo-row-title" to={e.to}>{e.title}</Link>
            {e.extra && <Typography.Text type="secondary">{e.extra}</Typography.Text>}<Tag>{e.tag}</Tag></div>)}
        </section>)}
  </main>;
}
