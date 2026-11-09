// Import payload parsing and the fill-only statements (ACs, comments, labels,
// PR links). Each child row is keyed by a stable source id, so a rerun inserts
// only what is missing and never overwrites what was changed in Mentat.
import type { Context } from 'hono';
import { hasScope } from '../../lib/guards';
import { newId } from './id';
import { now } from './store';
import { object, Problem, textField, type TodoEnv } from './types';
import { isHuman } from './kinds';
import { MAX_ACS, optionalText } from './item-fields';

/** Import writes history (done, dropped, a developer) directly: humans, or tokens with todo:import. */
export async function requireImporter(c: Context<TodoEnv>) {
  if (isHuman(c)) return;
  // The token was already resolved once, by the shared guard in auth.ts.
  const scopes = c.get('tokenScopes');
  if (!scopes || !hasScope(scopes, 'todo:import')) throw new Problem('import needs a human session or a todo:import token', 403);
}

const many = (v: unknown, name: string) => {
  if (v === undefined) return [];
  if (!Array.isArray(v) || v.length > 1000) throw new Problem(`${name} must be a list`);
  return v;
};
export function children(body: Record<string, unknown>) {
  if (Array.isArray(body.acs) && body.acs.length > MAX_ACS) throw new Problem(`acs must be a list of up to ${MAX_ACS}`);
  const acs = many(body.acs, 'acs').map(a => { const o = object(a); return { source_id: textField(o.source_id, 'acs[].source_id'), text: textField(o.text, 'acs[].text', 10000) }; });
  const comments = many(body.comments, 'comments').map(x => {
    const o = object(x);
    return { source_system: textField(o.source_system, 'comments[].source_system', 50), source_id: textField(o.source_id, 'comments[].source_id'),
      body: textField(o.body, 'comments[].body', 100000), source_author: optionalText(o.source_author, 'comments[].source_author', 200),
      source_created_at: optionalText(o.source_created_at, 'comments[].source_created_at', 40) };
  });
  const labels = many(body.labels, 'labels').map(l => textField(l, 'labels[]'));
  const links = many(body.links, 'links').map(x => {
    const o = object(x);
    if (o.kind !== undefined && o.kind !== 'pr') throw new Problem('imported links are pr links');
    if (typeof o.url !== 'string' || o.url.length > 2000 || !/^https?:\/\/\S+$/.test(o.url)) throw new Problem('links[].url must be an http(s) URL');
    return { url: o.url, title: optionalText(o.title, 'links[].title', 500) };
  });
  return { acs, comments, labels, links };
}
type Children = ReturnType<typeof children>;

/** What a rerun would still add; reads only. */
export async function missing(db: D1Database, id: string, k: Children) {
  const has = async (sql: string, ...args: unknown[]) => !!await db.prepare(sql).bind(...args).first();
  const out: Children = { acs: [], comments: [], labels: [], links: [] };
  for (const a of k.acs) if (!await has('SELECT 1 FROM backlog_ac WHERE source_id = ?', a.source_id)) out.acs.push(a);
  for (const m of k.comments) if (!await has('SELECT 1 FROM todo_comment WHERE source_system = ? AND source_id = ?', m.source_system, m.source_id)) out.comments.push(m);
  // Labels come only with a new item: a label removed in Mentat stays removed.
  for (const l of k.links) if (!await has("SELECT 1 FROM backlog_link WHERE item_id = ? AND kind = 'pr' AND url = ?", id, l.url)) out.links.push(l);
  return out;
}

/** Insert-if-absent statements; safe to replay, safe against a concurrent importer. */
export const EDITABLE_STAGE = "EXISTS (SELECT 1 FROM backlog_item WHERE task_id = ? AND stage IN ('draft','issued','taken'))";
export function fill(db: D1Database, id: string, actor: string, k: Children, existing = false) {
  const at = now();
  return [
    ...k.acs.map((a, i) => db.prepare(`INSERT INTO backlog_ac (id,item_id,position,text,created_by,created_at,source_id)
      SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM backlog_ac WHERE source_id = ?) AND (? = 0 OR ${EDITABLE_STAGE})`)
      .bind(newId(), id, `I${String(i).padStart(4, '0')}`, a.text, actor, at, a.source_id, a.source_id, existing ? 1 : 0, id)),
    ...k.comments.map(m => db.prepare(`INSERT INTO todo_comment (id,task_id,author_id,body,created_at,source_system,source_id,source_author,source_created_at)
      SELECT ?,?,?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM todo_comment WHERE source_system = ? AND source_id = ?)`)
      .bind(newId(), id, actor, m.body, m.source_created_at ?? at, m.source_system, m.source_id, m.source_author, m.source_created_at, m.source_system, m.source_id)),
    ...k.labels.flatMap(l => [
      db.prepare(`INSERT INTO todo_label (id,name,created_by,idem_key) SELECT ?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM todo_label WHERE name = ?)`)
        .bind(newId(), l, actor, `import-label:${l}`, l),
      db.prepare('INSERT OR IGNORE INTO todo_task_label SELECT ?, id FROM todo_label WHERE name = ?').bind(id, l),
    ]),
    ...k.links.map(l => db.prepare(`INSERT INTO backlog_link (id,item_id,kind,url,title,created_by,created_at) SELECT ?,?,'pr',?,?,?,?
      WHERE NOT EXISTS (SELECT 1 FROM backlog_link WHERE item_id = ? AND kind = 'pr' AND url = ? AND removed_at IS NULL)`)
      .bind(newId(), id, l.url, l.title, actor, at, id, l.url)),
  ];
}
