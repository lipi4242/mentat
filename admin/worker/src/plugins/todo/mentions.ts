import { marked, now } from './store';
export function extractHandles(body: string) {
  return [...new Set([...body.matchAll(/(?:^|[^\p{L}\p{N}_@.+-])@([a-z0-9_]{1,64})(?![\p{L}\p{N}_])/gu)].map(m => m[1]))];
}
export async function mentions(db: D1Database, body: string) {
  const handles = extractHandles(body);
  if (!handles.length) return [];
  return (await db.prepare(`SELECT id FROM todo_principal WHERE disabled_at IS NULL AND handle IN (SELECT value FROM json_each(?))`).bind(JSON.stringify(handles)).all<{ id: string }>()).results.map(p => p.id);
}
export function mentionStatements(db: D1Database, kind: string, source: string, ids: string[], op: string) {
  return [db.prepare(`DELETE FROM todo_mention WHERE source_kind = ? AND source_id = ? AND ${marked}`).bind(kind, source, op),
    ...ids.map(id => db.prepare(`INSERT INTO todo_mention (source_kind,source_id,principal_id,created_at) SELECT ?,?,?,? WHERE ${marked}`).bind(kind, source, id, now(), op))];
}
