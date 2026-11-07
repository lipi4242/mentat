// Acceptance criteria and links. Every change bumps the anchor's rev, so a
// submit or accept prepared against an older AC set ends in a 409.
import type { Context, Hono } from 'hono';
import { newId } from './id';
import { marked, mutate, now } from './store';
import { keys, object, Problem, type TodoEnv } from './types';
import { actorId } from './kinds';
import { mentions } from './mentions';
import { after } from './tree';
import { acText, MAX_ACS, optionalText } from './item-fields';
import { currentItem, getItem, requireDev, requirePm, type Item } from './item-store';

const EDITABLE = "EXISTS (SELECT 1 FROM backlog_item WHERE task_id = ? AND stage IN ('draft','issued','taken'))";
function editable(item: Item) {
  if (!['draft', 'issued', 'taken'].includes(item.stage)) throw new Problem(`ACs cannot change while the item is ${item.stage}`, 409, item);
}
async function owning(c: Context<TodoEnv>, table: 'backlog_ac' | 'backlog_link', allowed: string[]) {
  const body = object(await c.req.json()); keys(body, allowed);
  const row = await c.env.DB.prepare(`SELECT * FROM ${table} WHERE id = ? AND removed_at IS NULL`).bind(c.req.param('id')).first<{ id: string; item_id: string }>();
  if (!row) throw new Problem(`${table === 'backlog_ac' ? 'AC' : 'link'} not found`, 404);
  return { body, row, item: await currentItem(c, body, row.item_id) };
}
function pmOrDev(c: Context<TodoEnv>, item: Item) {
  try { requirePm(c, item); } catch { requireDev(c, item); }
}
const linkUrl = (v: unknown) => {
  if (typeof v !== 'string' || v.length > 2000 || !/^https?:\/\/\S+$/.test(v)) throw new Problem('url must be an http(s) URL');
  return v;
};

export function registerAcs(app: Hono<TodoEnv>) {
  app.post('/items/:id/acs', async c => {
    const body = object(await c.req.json()); keys(body, ['text', 'expected_rev']);
    const item = await currentItem(c, body); if (item instanceof Response) return item;
    requirePm(c, item); editable(item);
    const db = c.env.DB, text = acText(body.text), id = newId();
    const last = await db.prepare('SELECT max(position) AS p, count(removed_at IS NULL OR NULL) AS n FROM backlog_ac WHERE item_id = ?').bind(item.id).first<{ p: string | null; n: number }>();
    if ((last?.n ?? 0) >= MAX_ACS) throw new Problem(`an item has at most ${MAX_ACS} ACs`);
    return mutate(c, item, 'ac_added', {}, { diff: { ac_id: id, text }, view: getItem, recipients: await mentions(db, text),
      guard: EDITABLE, guardArgs: [item.id],
      related: op => [db.prepare(`INSERT INTO backlog_ac (id,item_id,position,text,created_by,created_at) SELECT ?,?,?,?,?,? WHERE ${marked}`)
        .bind(id, item.id, after(last?.p ?? null), text, actorId(c), now(), op)] });
  });
  app.patch('/acs/:id', async c => {
    const { body, row, item } = await owning(c, 'backlog_ac', ['text', 'expected_rev']); if (item instanceof Response) return item;
    requirePm(c, item); editable(item);
    const db = c.env.DB, text = acText(body.text);
    return mutate(c, item, 'ac_edited', {}, { diff: { ac_id: row.id, text }, view: getItem, recipients: await mentions(db, text),
      guard: EDITABLE, guardArgs: [item.id],
      related: op => [db.prepare(`UPDATE backlog_ac SET text = ? WHERE id = ? AND ${marked}`).bind(text, row.id, op)] });
  });
  app.post('/acs/:id/remove', async c => {
    const { row, item } = await owning(c, 'backlog_ac', ['expected_rev']); if (item instanceof Response) return item;
    requirePm(c, item); editable(item);
    return mutate(c, item, 'ac_removed', {}, { diff: { ac_id: row.id }, view: getItem, guard: EDITABLE, guardArgs: [item.id],
      related: op => [c.env.DB.prepare(`UPDATE backlog_ac SET removed_at = ? WHERE id = ? AND ${marked}`).bind(now(), row.id, op)] });
  });
  app.post('/items/:id/links', async c => {
    const body = object(await c.req.json()); keys(body, ['kind', 'url', 'task_id', 'title', 'expected_rev']);
    const item = await currentItem(c, body); if (item instanceof Response) return item;
    pmOrDev(c, item);
    const db = c.env.DB, kind = body.kind, title = optionalText(body.title, 'title', 500), id = newId();
    if (!['pr', 'issue', 'url', 'task'].includes(String(kind))) throw new Problem('kind must be pr, issue, url or task');
    const url = kind === 'task' ? null : linkUrl(body.url), task = kind === 'task' ? String(body.task_id ?? '') : null;
    if (kind === 'task' ? body.url != null : body.task_id != null) throw new Problem('a task link has task_id only; other links have url only');
    if (task !== null && !await db.prepare('SELECT 1 FROM todo_task WHERE id = ?').bind(task).first()) throw new Problem('task_id does not exist');
    const live = await db.prepare(`SELECT 1 FROM backlog_link WHERE item_id = ? AND removed_at IS NULL AND kind = ? AND (url = ? OR task_id = ?)`)
      .bind(item.id, kind, url, task).first();
    if (live) throw new Problem('this link already exists');
    return mutate(c, item, 'link_added', {}, { diff: { link_id: id, kind, url, task_id: task, title }, view: getItem, recipients: [item.dev_id ?? ''].filter(Boolean),
      related: op => [db.prepare(`INSERT INTO backlog_link (id,item_id,kind,url,task_id,title,created_by,created_at) SELECT ?,?,?,?,?,?,?,? WHERE ${marked}`)
        .bind(id, item.id, kind, url, task, title, actorId(c), now(), op)] });
  });
  app.post('/links/:id/remove', async c => {
    const { row, item } = await owning(c, 'backlog_link', ['expected_rev']); if (item instanceof Response) return item;
    pmOrDev(c, item);
    return mutate(c, item, 'link_removed', {}, { diff: { link_id: row.id }, view: getItem, recipients: [item.dev_id ?? ''].filter(Boolean),
      related: op => [c.env.DB.prepare(`UPDATE backlog_link SET removed_at = ? WHERE id = ? AND ${marked}`).bind(now(), row.id, op)] });
  });
}
