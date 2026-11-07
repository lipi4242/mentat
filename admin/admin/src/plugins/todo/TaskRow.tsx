import { Avatar, Button, Checkbox, Dropdown, Tooltip, Typography } from 'antd';
import { MinusCircleOutlined, MoreOutlined, PlusOutlined, SwapOutlined, SyncOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { DueChip } from './DueChip';
import { TaskProgress } from './TaskProgress';
import { repeatLabel } from './repeat';
import type { Principal, Task } from './meta';
export type RowActions = { toggle: (row: Task) => void; drop: (row: Task) => void; move: (row: Task) => void };
export function TaskRow({ row, principals, actions, onAdd, busy }: {
  row: Task; principals: Principal[]; actions: RowActions; onAdd: () => void; busy: boolean;
}) {
  const assignee = row.assignee_id !== row.owner_id && row.assignee_id && principals.find(p => p.id === row.assignee_id);
  return <div className={`todo-row${row.status === 'done' ? ' todo-done' : ''}`}>
    <Checkbox aria-label={`${row.title} ${row.status === 'done' ? 'újranyitása' : 'kész'}`} checked={row.status === 'done'}
      disabled={busy || row.status === 'dropped' || !!row.archived} onChange={() => actions.toggle(row)} />
    <Link className="todo-row-title" to={`/feladatok/${row.id}`}><Typography.Text delete={row.status === 'done'} type={row.status !== 'open' ? 'secondary' : undefined}>{row.title}</Typography.Text></Link>
    <div className="todo-signs">
      {row.due_date && <DueChip row={row} />}
      {row.repeat_rule && <Tooltip title={repeatLabel(row.repeat_rule)}><SyncOutlined aria-label={repeatLabel(row.repeat_rule)} /></Tooltip>}
      {assignee && <Tooltip title={`Nála a labda: ${assignee.display_name}${row.assignee_note ? `, következő lépés: ${row.assignee_note}` : ''}`}>
        <Avatar size={24} src={assignee.avatar} style={{ border: '1px solid #c9d0d4' }}>{assignee.display_name.slice(0, 1)}</Avatar></Tooltip>}
      <TaskProgress progress={row.progress} variant="ring" />
    </div>
    <div className="todo-row-actions">
      <Tooltip title="Részfeladat"><Button type="text" shape="circle" aria-label="Részfeladat" icon={<PlusOutlined />} onClick={onAdd} /></Tooltip>
      <Dropdown trigger={['click']} menu={{ items: [{ key: 'move', label: 'Áthelyezés', icon: <SwapOutlined /> },
        { key: 'drop', label: 'Elengedés', icon: <MinusCircleOutlined />, disabled: row.status === 'dropped' || busy }],
        onClick: ({ key }) => key === 'move' ? actions.move(row) : actions.drop(row) }}>
        <Tooltip title="Továbbiak"><Button type="text" shape="circle" aria-label="Továbbiak" icon={<MoreOutlined />} /></Tooltip>
      </Dropdown>
    </div>
  </div>;
}
