import { useRef, useState } from 'react';
import { apiSend, ApiError } from '../../lib/api';
import { API, type Task } from './meta';
export type WriteTask = (row: Task, set: Record<string, unknown>, action?: string) => Promise<Task>;
export function useTaskWrites(rows: Task[], reload: () => void) {
  const latest = useRef(new Map<string, Task>()), queue = useRef(Promise.resolve());
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  for (const row of rows) if ((latest.current.get(row.id)?.rev ?? 0) <= row.rev) latest.current.set(row.id, row);
  const write: WriteTask = (row, set, action) => {
    const run = queue.current.then(async () => {
      setBusy(true); setError('');
      try {
        const current = latest.current.get(row.id) ?? row;
        const result = await apiSend<Task>(action ? 'POST' : 'PATCH', `${API}/tasks/${row.id}${action ? `/${action}` : ''}`,
          { ...(action ? set : { set }), expected_rev: current.rev });
        latest.current.set(row.id, { ...current, ...result }); reload(); return result;
      } catch (e) {
        if (e instanceof ApiError && e.statusCode === 409) {
          const current = (e.body as { current?: Task })?.current;
          if (current) latest.current.set(row.id, current);
          setError('Közben valaki módosította, frissítettem.'); reload();
        } else setError((e as Error).message);
        throw e;
      } finally { setBusy(false); }
    });
    queue.current = run.then(() => {}, () => {});
    return run;
  };
  return { write, error, busy };
}
