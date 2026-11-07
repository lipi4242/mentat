import { useCallback, useState } from 'react';
import { Alert, Breadcrumb, Button, Dropdown, Skeleton, Tooltip, Typography } from 'antd';
import { ArrowLeftOutlined, CheckCircleFilled, CheckCircleOutlined, MinusCircleOutlined, MoreOutlined } from '@ant-design/icons';
import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../lib/useApi';
import { ApiError } from '../../lib/api';
import { API, tree, type Task, type Detail, type Label, type Principal } from './meta';
import { TaskFields } from './TaskFields';
import { TaskComments } from './TaskComments';
import { TaskLabels } from './TaskLabels';
import { TaskProgress } from './TaskProgress';
import { TaskAssignment } from './TaskAssignment';
import { EditableNote } from './EditableNote';
import { FirstRun } from './FirstRun';
import { TaskTree } from './TaskTree';
import { QuickAdd } from './QuickAdd';
import { MoveTask } from './MoveTask';
import { useTaskWrites } from './useTaskWrites';
import { useCompletion } from './useCompletion';
import { useVisibleReload } from './useVisibleReload';
export function TaskPage() {
  const { id } = useParams();
  const task = useApi<Detail>(id ? `${API}/tasks/${encodeURIComponent(id)}` : null);
  const tasks = useApi<Task[]>(`${API}/tasks`);
  const principals = useApi<Principal[]>(`${API}/principals`), labels = useApi<Label[]>(`${API}/labels`);
  const [move, setMove] = useState<Task | null>(null);
  const reload = useCallback(() => { task.reload(); tasks.reload(); }, [task.reload, tasks.reload]);
  const refresh = useCallback(() => { reload(); principals.reload(); labels.reload(); }, [reload, principals.reload, labels.reload]);
  useVisibleReload(refresh);
  const row = task.data?.id === id ? task.data : null;
  const all = tasks.data ?? [], { write, busy, error } = useTaskWrites([...all, ...(row ? [row, ...row.children] : [])], reload);
  const toggle = useCompletion(write);
  const drop = (r: Task) => { void write(r, { status: 'dropped' }).catch(() => {}); };
  const ancestors: Task[] = [], seen = new Set([id]);
  let parent = row?.parent_id;
  while (parent && !seen.has(parent)) {
    seen.add(parent);
    const found = all.find(t => t.id === parent); if (!found) break;
    ancestors.unshift(found); parent = found.parent_id;
  }
  const children = row ? tree(all.length ? all : row.children, false) : [];
  const subtree = (rows: ReturnType<typeof tree>): ReturnType<typeof tree> | undefined => {
    for (const r of rows) { if (r.id === id) return r.children ?? []; const found = subtree(r.children ?? []); if (found) return found; }
  };
  if (task.error instanceof ApiError && task.error.statusCode === 403) return <main className="todo-page todo-detail"><FirstRun onCreated={refresh} /></main>;
  return <main className="todo-page todo-detail">
    <nav className="todo-heading"><Tooltip title="Feladatok"><Link to="/feladatok" aria-label="Feladatok"><ArrowLeftOutlined /></Link></Tooltip>
      <Breadcrumb items={ancestors.map(a => ({ title: <Link to={`/feladatok/${a.id}`}>{a.title}</Link> }))} /></nav>
    {(task.error || tasks.error || principals.error || labels.error || error) &&
      <Alert type="info" message={error || task.error?.message || tasks.error?.message || principals.error?.message || labels.error?.message} />}
    {!row ? task.loading && <Skeleton active /> : <div key={row.id}>
      <header className="todo-heading todo-title">
        <Tooltip title={row.status === 'open' ? 'Kész' : 'Újranyitás'}><Button type="text" shape="circle"
          aria-label={row.status === 'open' ? 'Kész' : 'Újranyitás'} disabled={busy || !!row.archived}
          className={row.status === 'done' ? 'todo-complete' : ''} icon={row.status === 'done' ? <CheckCircleFilled /> : <CheckCircleOutlined />}
          onClick={() => void toggle(row)} /></Tooltip>
        <Typography.Title level={3} editable={{ tooltip: 'Cím szerkesztése', onChange: title => {
          if (title.trim() && title !== row.title) void write(row, { title: title.trim() }).catch(() => {});
        } }}>{row.title}</Typography.Title>
        <Dropdown trigger={['click']} menu={{ items: [{ key: 'drop', label: 'Elengedés', icon: <MinusCircleOutlined />, disabled: busy || row.status === 'dropped' }], onClick: () => drop(row) }}>
          <Tooltip title="Továbbiak"><Button type="text" shape="circle" aria-label="Továbbiak" icon={<MoreOutlined />} /></Tooltip>
        </Dropdown>
      </header>
      <div className="todo-properties"><TaskFields row={row} principals={principals.data ?? []} write={write} />
        <TaskLabels row={row} labels={labels.data ?? []} write={write} /></div>
      <TaskAssignment row={row} principals={principals.data ?? []} write={write} busy={busy} />
      <section className="todo-section"><EditableNote value={row.description} label="Jegyzet…" save={description => write(row, { description })} /></section>
      <section className="todo-section" aria-label="Részfeladatok">
        <TaskProgress progress={row.progress} />
        {!!row.children.length && <TaskTree rows={subtree(children) ?? tree(row.children, false)} principals={principals.data ?? []}
          actions={{ toggle, drop, move: setMove }} busy={busy} onSaved={reload} storageKey={`todo:detail:${row.id}`} expandAll />}
        <QuickAdd parent={row.id} onSaved={reload} />
      </section>
      <TaskComments row={row} principals={principals.data ?? []} write={write} />
    </div>}
    {move && <MoveTask row={move} rows={all} onClose={() => setMove(null)} onSaved={reload} />}
  </main>;
}
