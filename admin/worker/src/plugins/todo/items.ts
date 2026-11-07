import type { Hono } from 'hono';
import { newId } from './id';
import { event, marked, mutate, now } from './store';
import { keys, object, Problem, textField, type Task, type TodoEnv } from './types';
import { after, appendPosition } from './tree';
import { mentions, mentionStatements } from './mentions';
import { actorId, checkParent, handleId } from './kinds';
import { findProject } from './projects';
import { acTexts, itemFields, SPEC_FIELDS } from './item-fields';
import { currentItem, getItem, ITEM_SELECT, itemDetail, requirePm, resolveRef, STAGES } from './item-store';

export function registerItems(app: Hono<TodoEnv>) {
  app.post('/items', async c => {
    const body = object(await c.req.json());
    keys(body, ['project', 'parent', 'acs', 'idem_key', ...SPEC_FIELDS]);
    const db = c.env.DB, actor = actorId(c), key = textField(body.idem_key, 'idem_key');
    const replay = async () => {
      const row = await db.prepare('SELECT id, kind FROM todo_task WHERE created_by = ? AND idem_key = ?').bind(actor, key).first<Task>();
      if (row && row.kind !== 'item') throw new Problem('idem_key was already used for a task that is not an item');
      return row && getItem(db, row.id);
    };
    const existing = await replay(); if (existing) return c.json(existing);
    if (!('title' in body)) throw new Problem('title must be nonempty text, max 1000');
    const project = await findProject(db, body.project);
    const { task, item } = await itemFields(db, body);
    const parent = body.parent == null ? null : String(body.parent);
    await checkParent(db, 'item', parent, project.id);
    const id = newId(), at = now(), acs = acTexts(body.acs);
    const values = { status: 'open', tz: 'Europe/Budapest', repeat_from: 'schedule', parent_id: parent,
      position: await appendPosition(db, parent), owner_id: project.default_pm_id ?? actor, ...task,
      id, kind: 'item', idem_key: key, created_by: actor, updated_by: actor, created_at: at, updated_at: at };
    const ext = { task_id: id, project_id: project.id, ...item };
    const ids = await mentions(db, `${task.description ?? ''}\n${acs.join('\n')}`);
    let position: string | null = null;
    try {
      await db.batch([
        db.prepare(`INSERT INTO todo_task (${Object.keys(values).join(',')}) VALUES (${Object.keys(values).map(() => '?').join(',')})`).bind(...Object.values(values)),
        // Numbering inside the batch: a replay or a failed create never allocates a number.
        db.prepare(`INSERT INTO backlog_item (${Object.keys(ext).join(',')}, number)
          SELECT ${Object.keys(ext).map(() => '?').join(',')}, next_number FROM backlog_project WHERE id = ?`).bind(...Object.values(ext), project.id),
        db.prepare('UPDATE backlog_project SET next_number = next_number + 1 WHERE id = ?').bind(project.id),
        ...acs.map(text => db.prepare('INSERT INTO backlog_ac (id,item_id,position,text,created_by,created_at) VALUES (?,?,?,?,?,?)')
          .bind(newId(), id, position = after(position), text, actor, at)),
        ...ids.map(p => db.prepare(`INSERT INTO todo_mention VALUES ('task',?,?,?)`).bind(id, p, at)),
        event(db, actor, 'created', { ...values, ...ext, acs }, [String(values.owner_id), ...ids], id),
      ]);
    } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) { const won = await replay(); if (won) return c.json(won); }
      throw e;
    }
    return c.json(await getItem(db, id), 201);
  });

  app.get('/items', async c => {
    const q = c.req.query(), db = c.env.DB, where = ['1'], args: unknown[] = [];
    if (q.project !== undefined) { where.push('b.project_id = ?'); args.push((await findProject(db, q.project)).id); }
    if (q.stage !== undefined) {
      const stages = q.stage.split(',');
      if (stages.some(s => !(STAGES as readonly string[]).includes(s))) throw new Problem(`stage must be one or more of ${STAGES.join(', ')}`);
      where.push(`b.stage IN (${stages.map(() => '?').join(',')})`); args.push(...stages);
    }
    if (q.pm !== undefined) { where.push('t.owner_id = ?'); args.push(await handleId(db, 'pm', q.pm)); }
    if (q.dev !== undefined) { where.push('b.dev_id = ?'); args.push(await handleId(db, 'dev', q.dev)); }
    if (q.ball !== undefined) { where.push('coalesce(t.assignee_id, t.owner_id) = ?'); args.push(await handleId(db, 'ball', q.ball)); }
    if (q.older_than !== undefined) {
      if (!/^\d{1,5}$/.test(q.older_than)) throw new Problem('older_than must be a number of days');
      // An issued item counts from its issue: a comment must not hide "issued, not taken" from the PM.
      where.push("julianday(CASE WHEN b.stage = 'issued' THEN coalesce(b.issued_at, t.updated_at) ELSE t.updated_at END) <= julianday('now') - ?");
      args.push(Number(q.older_than));
    }
    const { results } = await db.prepare(`${ITEM_SELECT} WHERE ${where.join(' AND ')} ORDER BY t.position, t.id`).bind(...args).all();
    return c.json(results, 200, { 'X-Total-Count': String(results.length) });
  });

  app.get('/items/:ref', async c => c.json(await itemDetail(c.env.DB, await resolveRef(c.env.DB, c.req.param('ref')))));

  app.patch('/items/:id', async c => {
    const body = object(await c.req.json()); keys(body, ['set', 'expected_rev']);
    const input = object(body.set); keys(input, SPEC_FIELDS);
    const item = await currentItem(c, body); if (item instanceof Response) return item;
    requirePm(c, item);
    const db = c.env.DB, { task, item: ext } = await itemFields(db, input);
    if (!Object.keys(task).length && !Object.keys(ext).length) throw new Problem('set must contain a field');
    const changed = 'description' in task;
    const ids = changed ? await mentions(db, String(task.description ?? '')) : [];
    return mutate(c, item, 'item_updated', task, { diff: { ...task, ...ext }, recipients: [item.dev_id ?? '', ...ids].filter(Boolean), view: getItem,
      guard: "EXISTS (SELECT 1 FROM todo_task WHERE id = ? AND kind = 'item')", guardArgs: [item.id],
      related: op => [...(changed ? mentionStatements(db, 'task', item.id, ids, op) : []),
        ...(Object.keys(ext).length ? [db.prepare(`UPDATE backlog_item SET ${Object.keys(ext).map(k => `${k} = ?`).join(',')} WHERE task_id = ? AND ${marked}`)
          .bind(...Object.values(ext), item.id, op)] : [])] });
  });
}
