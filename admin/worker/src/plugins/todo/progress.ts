import type { Task } from './types';

export type Progress = { done: number; total: number; percent: number };

// Count leaves bottom-up in the full tree, independent of list filters. An
// explicit queue supports arbitrary depth without exhausting the JS stack.
export async function withProgress<T extends { id: string }>(db: D1Database, rows: T[]) {
  if (!rows.length) return [];
  const { results } = await db.prepare('SELECT id,parent_id,status FROM todo_task')
    .all<Pick<Task, 'id' | 'parent_id' | 'status'>>();
  const nodes = new Map(results.map(row => [row.id, { ...row, children: 0, remaining: 0, done: 0, total: 0 }]));
  for (const node of nodes.values()) {
    const parent = node.parent_id && nodes.get(node.parent_id);
    if (parent) { parent.children++; parent.remaining++; }
  }
  const queue = [...nodes.values()].filter(node => !node.children);
  for (const leaf of queue) {
    leaf.total = leaf.status === 'dropped' ? 0 : 1;
    leaf.done = leaf.status === 'done' ? 1 : 0;
  }
  for (let i = 0; i < queue.length; i++) {
    const node = queue[i], parent = node.parent_id && nodes.get(node.parent_id);
    if (!parent) continue;
    // A dropped branch contributes no leaves to any of its ancestors.
    if (node.status !== 'dropped') { parent.done += node.done; parent.total += node.total; }
    if (--parent.remaining === 0) queue.push(parent);
  }
  return rows.map(row => {
    const node = nodes.get(row.id);
    const progress: Progress | null = node?.children
      ? { done: node.done, total: node.total, percent: node.total ? Math.round(100 * node.done / node.total) : 0 }
      : null;
    return { ...row, progress };
  });
}
