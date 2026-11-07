import { useEffect, useState, type Key, type ReactNode } from 'react';
import { Table } from 'antd';
import { TaskRow, type RowActions } from './TaskRow';
import { QuickAdd } from './QuickAdd';
import { flatten, type Principal, type TreeTask } from './meta';
function stored(key: string): { keys: Key[]; seen: string[] } {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? 'null');
    if (Array.isArray(value?.keys) && Array.isArray(value?.seen)) return value;
  } catch { /* Storage is optional. */ }
  return { keys: [], seen: [] };
}
export function TaskTree({ rows, principals, actions, busy, onSaved, storageKey, expandAll = false, empty }: {
  rows: TreeTask[]; principals: Principal[]; actions: RowActions; busy: boolean; onSaved: () => void;
  storageKey: string; expandAll?: boolean; empty?: ReactNode;
}) {
  const [expanded, setExpanded] = useState(() => stored(storageKey)), [add, setAdd] = useState<string | null>(null);
  useEffect(() => { setExpanded(stored(storageKey)); }, [storageKey]);
  const parents = flatten(rows).filter(row => row.children?.length).map(row => row.id).join('|');
  useEffect(() => {
    const ids = parents ? parents.split('|') : [];
    setExpanded(prev => {
      const fresh = ids.filter(id => !prev.seen.includes(id));
      if (!fresh.length) return prev;
      const next = { keys: expandAll ? [...prev.keys, ...fresh] : prev.keys, seen: [...prev.seen, ...fresh] };
      try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Storage is optional. */ }
      return next;
    });
  }, [parents, expandAll, storageKey]);
  return <Table<TreeTask> className="todo-tree" rowKey="id" showHeader={false} pagination={false} dataSource={rows}
    locale={{ emptyText: empty }} expandable={{ indentSize: 28, expandedRowKeys: expanded.keys,
      onExpandedRowsChange: keys => {
        const next = { ...expanded, keys: [...keys] }; setExpanded(next);
        try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Storage is optional. */ }
      } }} columns={[{ key: 'task', render: (_, row) => <>
      <TaskRow row={row} principals={principals} busy={busy} actions={actions} onAdd={() => setAdd(add === row.id ? null : row.id)} />
      {add === row.id && <div className="todo-child-add"><QuickAdd parent={row.id} autoFocus onSaved={onSaved} /></div>}
    </> }]} />;
}
