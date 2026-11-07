import type { Hono } from 'hono';
import { newId } from './id';
import { event, getTask, current, mutate, now } from './store';
import { fields, validateTask } from './validate';
import { keys, object, Problem, textField, type Task, type TodoEnv } from './types';
import { appendPosition } from './tree';
import { mentions, mentionStatements } from './mentions';
import { checkParent, isHuman, refuseItem } from './kinds';
import { caseDetail, caseFields, caseInsert, caseUpdate } from './case-fields';
const RECURRING_CASE = 'a case cannot repeat; recurring obligations belong to the cases plugin';
export function registerWrite(app: Hono<TodoEnv>) {
  app.post('/tasks', async c => {
    const { kind = 'todo', case: caseBody, ...body } = object(await c.req.json());
    const actor = c.get('principal')!.id, db = c.env.DB;
    if (kind === 'item') throw new Problem('create backlog items with POST /items');
    if (kind !== 'todo' && kind !== 'case') throw new Problem('kind must be todo or case');
    if (caseBody !== undefined && kind !== 'case') throw new Problem('case fields require kind case');
    const key = textField(body.idem_key, 'idem_key');
    const replay = () => db.prepare('SELECT * FROM todo_task WHERE created_by = ? AND idem_key = ?').bind(actor, key).first<Task>();
    const show = async (row: Task) => caseDetail(db, row);
    const existing = await replay(); if (existing) return c.json(await show(existing));
    const set = fields(body, true);
    if (kind === 'case' && set.repeat_rule != null) throw new Problem(RECURRING_CASE);
    const extension = kind === 'case' ? caseFields(caseBody ?? {}) : null;
    const id = newId(), at = now(), parent = (set.parent_id ?? null) as string | null;
    await checkParent(db, kind, parent);
    const values = { status: 'open', tz: 'Europe/Budapest', repeat_from: 'schedule', owner_id: actor,
      parent_id: parent, position: set.position ?? await appendPosition(db, parent), ...set,
      id, kind, created_by: actor, updated_by: actor, created_at: at, updated_at: at };
    await validateTask(db, values);
    const ids = await mentions(db, String(set.description ?? ''));
    const stmts = [db.prepare(`INSERT INTO todo_task (${Object.keys(values).join(',')}) VALUES (${Object.keys(values).map(() => '?').join(',')})`).bind(...Object.values(values)),
      ...(extension ? [caseInsert(db, id, extension, actor, isHuman(c))] : []),
      ...ids.map(p => db.prepare(`INSERT INTO todo_mention VALUES ('task',?,?,?)`).bind(id, p, at)),
      event(db, actor, 'created', extension ? { ...values, case: extension } : values, [String(values.owner_id), ...(set.assignee_id ? [String(set.assignee_id)] : []), ...ids], id)];
    try { await db.batch(stmts); } catch (e) {
      if (/UNIQUE constraint/i.test(String(e))) { const won = await replay(); if (won) return c.json(await show(won)); }
      throw e;
    }
    return c.json(await show((await getTask(db, id))!), 201);
  });
  app.patch('/tasks/:id', async c => {
    const body = object(await c.req.json()); keys(body, ['set','case','expected_rev']);
    const row = await current(c, body); if (row instanceof Response) return row;
    refuseItem(row, 'PATCH /tasks');
    if (body.case !== undefined && row.kind !== 'case') throw new Problem('case fields require a case');
    const extension = body.case === undefined ? {} : caseFields(body.case);
    const set = body.set === undefined && body.case !== undefined ? {} : fields(body.set);
    if (row.kind === 'case' && set.repeat_rule != null) throw new Problem(RECURRING_CASE);
    if (!Object.keys(set).length && !Object.keys(extension).length) throw new Problem('set must contain a field');
    await validateTask(c.env.DB, set, row);
    const changed = 'description' in set;
    const ids = changed ? await mentions(c.env.DB, String(set.description ?? '')) : [];
    return mutate(c, row, 'updated', set, { recipients: ids,
      diff: Object.keys(extension).length ? { ...set, case: extension } : set,
      view: (db, id) => getTask(db, id).then(t => t && caseDetail(db, t)),
      related: op => [...(changed ? mentionStatements(c.env.DB, 'task', row.id, ids, op) : []),
        ...(Object.keys(extension).length ? [caseUpdate(c.env.DB, row.id, extension, op)] : [])] });
  });
}
