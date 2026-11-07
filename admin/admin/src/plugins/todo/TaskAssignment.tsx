import { Avatar, Button, Tooltip } from 'antd';
import { ArrowRightOutlined, RollbackOutlined } from '@ant-design/icons';
import type { Detail, Principal } from './meta';
import type { WriteTask } from './useTaskWrites';
import { EditableNote } from './EditableNote';
export function TaskAssignment({ row, principals, write, busy }: { row: Detail; principals: Principal[]; write: WriteTask; busy: boolean }) {
  if (!row.assignee_id) return null;
  const avatar = (id: string) => {
    const person = principals.find(p => p.id === id);
    return <Tooltip title={person?.display_name}><Avatar size={32} src={person?.avatar}>{person?.display_name.slice(0, 1)}</Avatar></Tooltip>;
  };
  return <div className="todo-assignment">
    {avatar(row.owner_id)}<ArrowRightOutlined />{avatar(row.assignee_id)}
    <EditableNote value={row.assignee_note} label="Következő lépés…" save={assignee_note => write(row, { assignee_note })} />
    <Tooltip title="Visszaadom"><Button type="text" shape="circle" aria-label="Visszaadom" icon={<RollbackOutlined />}
      disabled={busy || row.status !== 'open'} onClick={() => void write(row, {}, 'handback').catch(() => {})} /></Tooltip>
  </div>;
}
