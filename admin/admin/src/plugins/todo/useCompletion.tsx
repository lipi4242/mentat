import { App, Button } from 'antd';
import { RollbackOutlined, SyncOutlined } from '@ant-design/icons';
import { dateLabel, type Task } from './meta';
import type { WriteTask } from './useTaskWrites';
export function useCompletion(write: WriteTask, onDone?: (id: string) => void) {
  const { message } = App.useApp();
  return async (row: Task) => {
    try {
      if (row.status !== 'open') { await write(row, { status: 'open' }); return; }
      const result = await write(row, {}, 'complete');
      if (row.repeat_rule) {
        const date = dateLabel({ ...row, ...result });
        message.open({ content: <><SyncOutlined /> {date.charAt(0).toUpperCase() + date.slice(1)} újra itt van</>, duration: 5 });
      } else {
        onDone?.(row.id);
        const key = `done:${row.id}`;
        message.open({ key, duration: 5, content: <>Kész <Button type="link" icon={<RollbackOutlined />}
          onClick={() => { void write(result, { status: 'open' }).then(() => message.destroy(key)).catch(() => {}); }}>Visszavonom</Button></> });
      }
    } catch { /* The shared writer displays the failure. */ }
  };
}
