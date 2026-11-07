// Linear import (SPEC §6): one batch per item, keyed by ext_ref. A rerun only
// fills missing child rows; it never changes an item already in Mentat.
import type { Hono } from 'hono';
import { newId } from './id';
import { event, mutate, now } from './store';
import { keys, object, Problem, textField, type TodoEnv } from './types';
import { appendPosition, treeGuard } from './tree';
import { actorId, checkParent, enabledPrincipal } from './kinds';
import { findProject } from './projects';
import { itemFields, MAX_ACS } from './item-fields';
import { getItem } from './item-store';
import { children, fill, missing, requireImporter } from './import-fill';

const FIELDS = ['ext_ref', 'project', 'number', 'title', 'description', 'priority', 'estimate', 'stage', 'dev', 'archived',
  'created_at', 'labels', 'acs', 'comments', 'links', 'idem_key'];
const byExt = (db: D1Database, ext: string) => db.prepare('SELECT task_id FROM backlog_item WHERE ext_ref = ?').bind(ext).first<{ task_id: string }>();

export function registerImport(app: Hono<TodoEnv>) {
  app.post('/items/import', async c => {
    await requireImporter(c);
    const body = object(await c.req.json()); keys(body, FIELDS);
    const db = c.env.DB, actor = actorId(c), ext = textField(body.ext_ref, 'ext_ref'), kids = children(body);
    const existing = async () => {
      const row = await byExt(db, ext); if (!row) return null;
      const add = await missing(db, row.task_id, kids), item = (await getItem(db, row.task_id))!;
      // An existing item takes new ACs only while they are editable; review and later stay frozen.
      const skipped = { acs: ['draft', 'issued', 'taken'].includes(item.stage) ? 0 : add.acs.length };
      if (skipped.acs) add.acs = [];
      if (add.acs.length && (await db.prepare('SELECT count(*) AS n FROM backlog_ac WHERE item_id = ? AND removed_at IS NULL').bind(row.task_id).first<{ n: number }>())!.n + add.acs.length > MAX_ACS) throw new Problem(`an item has at most ${MAX_ACS} ACs`);
      const counts = { acs: add.acs.length, comments: add.comments.length, labels: add.labels.length, links: add.links.length };
      if (Object.values(counts).some(Boolean)) {
        await db.batch([...fill(db, row.task_id, actor, add, true), event(db, actor, 'import_filled', { ext_ref: ext, ...counts }, [actor], row.task_id),
          db.prepare('UPDATE todo_task SET rev = rev + 1, updated_at = ?, updated_by = ? WHERE id = ?').bind(now(), actor, row.task_id)]);
      }
      return c.json({ id: row.task_id, key: item.key, created: false, added: counts, skipped });
    };
    const found = await existing(); if (found) return found;
    const project = await findProject(db, body.project);
    if (!Number.isSafeInteger(body.number) || (body.number as number) < 1) throw new Problem('number must be a positive integer');
    const stage = String(body.stage);
    if (!['draft', 'taken', 'done', 'dropped'].includes(stage)) throw new Problem('an imported stage is draft, taken, done or dropped');
    const dev = body.dev == null ? null : await enabledPrincipal(db, body.dev, 'dev');
    if ((stage === 'taken') !== (dev !== null)) throw new Problem('a taken item needs a dev, and only a taken item has one');
    if (typeof body.archived !== 'boolean' && body.archived !== undefined) throw new Problem('archived must be true or false');
    const { task, item } = await itemFields(db, { title: body.title, description: body.description ?? null,
      ...(body.priority !== undefined ? { priority: body.priority } : {}), ...(body.estimate !== undefined ? { estimate: body.estimate } : {}) });
    const at = now(), id = newId(), created = typeof body.created_at === 'string' && !Number.isNaN(Date.parse(body.created_at)) ? body.created_at : at;
    const status = stage === 'done' ? 'done' : stage === 'dropped' ? 'dropped' : 'open';
    const values = { ...task, id, kind: 'item', status, tz: 'Europe/Budapest', repeat_from: 'schedule', parent_id: null,
      position: await appendPosition(db, null), owner_id: project.default_pm_id ?? actor, assignee_id: dev,
      archived: body.archived ? 1 : 0, idem_key: textField(body.idem_key ?? `import:${ext}`, 'idem_key'),
      done_at: status === 'done' ? at : null, done_by: status === 'done' ? actor : null,
      created_by: actor, updated_by: actor, created_at: created, updated_at: at };
    const ext_row = { ...item, task_id: id, project_id: project.id, number: body.number as number, stage, dev_id: dev, ext_ref: ext,
      taken_at: stage === 'taken' ? at : null };
    const insert = (table: string, row: Record<string, unknown>) =>
      db.prepare(`INSERT INTO ${table} (${Object.keys(row).join(',')}) VALUES (${Object.keys(row).map(() => '?').join(',')})`).bind(...Object.values(row));
    try {
      await db.batch([insert('todo_task', values), insert('backlog_item', ext_row),
        db.prepare('UPDATE backlog_project SET next_number = max(next_number, ? + 1) WHERE id = ?').bind(body.number, project.id),
        ...fill(db, id, actor, kids), event(db, actor, 'imported', { ext_ref: ext, stage, number: body.number }, [String(values.owner_id), ...(dev ? [dev] : [])], id)]);
    } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) {
        const won = await existing(); if (won) return won;
        throw new Problem(`${project.prefix}-${body.number} already exists in Mentat`, 409);
      }
      throw e;
    }
    return c.json({ id, key: `${project.prefix}-${body.number}`, created: true,
      added: { acs: kids.acs.length, comments: kids.comments.length, labels: kids.labels.length, links: kids.links.length }, skipped: { acs: 0 } }, 201);
  });

  app.post('/items/import/parent', async c => {
    await requireImporter(c);
    const body = object(await c.req.json()); keys(body, ['ext_ref', 'parent_ext_ref']);
    const db = c.env.DB, child = await byExt(db, textField(body.ext_ref, 'ext_ref')), parent = await byExt(db, textField(body.parent_ext_ref, 'parent_ext_ref'));
    if (!child || !parent) throw new Problem('both items must be imported first', 404);
    const row = (await getItem(db, child.task_id))!;
    if (row.parent_id !== null) return c.json(row); // fill-only: never re-parent
    await checkParent(db, 'item', parent.task_id, row.project_id);
    const args = [row.id, parent.task_id];
    if (!(await db.prepare(`SELECT ${treeGuard} AS ok`).bind(...args).first<{ ok: number }>())?.ok) throw new Problem('parent would create a tree cycle');
    return mutate(c, row, 'moved', { parent_id: parent.task_id, position: await appendPosition(db, parent.task_id) },
      { guard: `${treeGuard} AND EXISTS (SELECT 1 FROM todo_task WHERE id = ? AND parent_id IS NULL)`, guardArgs: [...args, row.id], view: getItem });
  });
}
