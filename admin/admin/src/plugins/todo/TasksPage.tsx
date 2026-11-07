import { useCallback, useRef, useState } from 'react';
import { Alert, Button, Collapse, Segmented, Skeleton, Tooltip, Typography } from 'antd';
import { ApartmentOutlined, HistoryOutlined, SunOutlined } from '@ant-design/icons';
import { useApi } from '../../lib/useApi';
import { ApiError } from '../../lib/api';
import { API, flatten, tree, type Principal, type Task } from './meta';
import { FirstRun } from './FirstRun';
import { QuickAdd } from './QuickAdd';
import { MoveTask } from './MoveTask';
import { TaskTree } from './TaskTree';
import { useTaskWrites } from './useTaskWrites';
import { useCompletion } from './useCompletion';
import { useVisibleReload } from './useVisibleReload';
export function TasksPage() {
  const tasks = useApi<Task[]>(`${API}/tasks`), principals = useApi<Principal[]>(`${API}/principals`);
  const [view, setView] = useState('Most'), [move, setMove] = useState<Task | null>(null);
  const [justDone, setJustDone] = useState(new Set<string>()), add = useRef<HTMLDivElement>(null);
  const { write, error, busy } = useTaskWrites(tasks.data ?? [], tasks.reload);
  const toggle = useCompletion(write, id => setJustDone(prev => new Set([...prev, id])));
  const visibleReload = useCallback(() => { setJustDone(new Set()); tasks.reload(); principals.reload(); }, [tasks.reload, principals.reload]);
  useVisibleReload(visibleReload);
  const rows = tree(tasks.data ?? [], view === 'Most', justDone), shown = new Set(flatten(rows).map(r => r.id));
  const older = tree(flatten(tree(tasks.data ?? [], true, new Set(), true)).filter(r => !shown.has(r.id)), false);
  const actions = { toggle, move: setMove, drop: (row: Task) => { void write(row, { status: 'dropped' }).catch(() => {}); } };
  if (tasks.error instanceof ApiError && tasks.error.statusCode === 403) return <main className="todo-page"><FirstRun onCreated={visibleReload} /></main>;
  const empty = <div className="todo-empty">
    {view === 'Most' ? <SunOutlined /> : <ApartmentOutlined />}
    <p>{view === 'Most' ? 'Most van egy kis tér.' : 'Még nincs feladatod.'}</p>
    <Button onClick={() => add.current?.querySelector('input')?.focus()}>Adj hozzá egyet</Button>
  </div>;
  return <main className="todo-page">
    <header className="todo-heading"><Typography.Title level={4}>Feladatok</Typography.Title>
      <Tooltip title={view === 'Most' ? 'Ma, a következő napok és a dátum nélküli feladatok.' : 'Minden feladat, a kész és elengedett tételekkel.'}>
        <Segmented value={view} onChange={v => setView(String(v))} options={[
          { value: 'Most', label: 'Most', icon: <SunOutlined /> }, { value: 'Minden', label: 'Minden', icon: <ApartmentOutlined /> }]} />
      </Tooltip>
    </header>
    {(tasks.error || principals.error || error) && <Alert type="info" message={error || tasks.error?.message || principals.error?.message} />}
    <div ref={add}><QuickAdd parent={null} onSaved={tasks.reload} /></div>
    {tasks.loading && !tasks.data ? <Skeleton active /> : <TaskTree key={view} rows={rows} principals={principals.data ?? []} actions={actions}
      busy={busy} onSaved={tasks.reload} storageKey={`todo:expanded:${view}`} expandAll={view === 'Most'} empty={empty} />}
    {view === 'Most' && !!older.length && <Collapse ghost items={[{ key: 'older', label: <><HistoryOutlined /> Régebbről maradt</>, children:
      <TaskTree rows={older} principals={principals.data ?? []} actions={actions} busy={busy} onSaved={tasks.reload} storageKey="todo:expanded:older" /> }]} />}
    {move && <MoveTask row={move} rows={tasks.data ?? []} onClose={() => setMove(null)} onSaved={tasks.reload} />}
  </main>;
}
