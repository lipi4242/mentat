import { CalendarOutlined, HistoryOutlined } from '@ant-design/icons';
import { dateLabel, today, type Task } from './meta';
export function DueChip({ row }: { row: Task }) {
  const past = !!row.due_date && row.due_date < today(row.tz);
  return <span className={`todo-due${row.due_date === today(row.tz) ? ' todo-today' : ''}`}>
    {past ? <HistoryOutlined /> : <CalendarOutlined />} {dateLabel(row)}
  </span>;
}
