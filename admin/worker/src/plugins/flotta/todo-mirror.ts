// A kiosztott incidens a menedzser (managers.ts lánca) labdája: egy todo-feladat, aminek ő a
// gazdája. Az ágens a meglévő todo-pollal (`mentat-todo ball` / `changes`) látja, új pollozás
// nincs. A feladat CSAK vetület (flotta-menedzser): az állapot és az audit a flotta_incident /
// flotta_repair_op sorokban él, a kommentbe összefoglaló megy. Ugyanazokat a todo-sorokat és
// eseményeket írjuk, amiket a todo API írna, hogy a változásfolyam lássa őket.
// A szerző mindig a rendszer saját résztvevője (system-principal.ts), a gazda a menedzser.
// Óránként legfeljebb max_tasks_per_hour új feladat; a többi incidens addig várakozik
// (a levél-út viszi), és egy összegző incidens jelzi a visszatartást (limits.ts).
import { newId } from '../todo/id';
import { event as todoEvent } from '../todo/store';
import { appendPosition } from '../todo/tree';
import { event, iso, OVERLOAD, type Fleet, type Row } from './types';
import { overload, tasksLastHour } from './limits';
import { ensureSystemPrincipal } from './system-principal';
import { closeNote, instructions, title } from './task-text';

const SELECT = 'SELECT i.*, b.name AS box_name FROM flotta_incident i JOIN flotta_box b ON b.id = i.box_id';

async function createTask(db: D1Database, fleet: Fleet, inc: Row, owner: string, system: string, at: Date): Promise<string> {
  const key = `flotta:${inc.id}:${inc.handovers}:${owner}:${inc.assigned_at}`;   // kiosztásonként egy (box-várakozás után is új)
  // kiosztásonként egy feladat, akárki is a gazdája (egy korábbi kör alatt is létrejöhetett)
  const replay = () => db.prepare('SELECT id FROM todo_task WHERE idem_key = ?1 ORDER BY created_at LIMIT 1').bind(key).first<{ id: string }>();
  const had = await replay();
  if (had) return had.id;
  const id = newId(), now = iso(at);
  const values = { id, parent_id: null, position: await appendPosition(db, null), title: title(inc), description: instructions(fleet, inc),
    status: 'open', tz: 'Europe/Budapest', owner_id: owner, repeat_from: 'schedule', kind: 'todo', idem_key: key,
    created_at: now, created_by: system, updated_at: now, updated_by: system };
  try {
    await db.batch([
      db.prepare(`INSERT INTO todo_task (${Object.keys(values).join(',')}) VALUES (${Object.keys(values).map(() => '?').join(',')})`).bind(...Object.values(values)),
      todoEvent(db, system, 'created', values, [owner], id),
    ]);
  } catch (e) {
    const won = /UNIQUE constraint/i.test(String(e)) ? await replay() : null;
    if (!won) throw e;
    return won.id;
  }
  return id;
}

/** Komment, majd kész — mindkettő a todo saját rev-őrével, hogy egy közbeeső írás ne vesszen el. */
async function closeTask(db: D1Database, actor: string, taskId: string, note: string, at: Date) {
  const task = await db.prepare(`SELECT rev, status, owner_id FROM todo_task WHERE id = ?1`).bind(taskId).first<{ rev: number; status: string; owner_id: string }>();
  if (!task || task.status !== 'open') return false;
  const now = iso(at), c = newId(), op1 = newId(), op2 = newId();
  const guarded = (op: string, kind: string, diff: unknown, rev: number) => db.prepare(`INSERT INTO todo_event (op_id,task_id,at,actor_id,kind,diff_json,recipients_json)
      SELECT ?,?,?,?,?,?,? WHERE EXISTS (SELECT 1 FROM todo_task WHERE id = ? AND rev = ? AND status = 'open')`)
    .bind(op, taskId, now, actor, kind, JSON.stringify(diff), JSON.stringify([task.owner_id]), taskId, rev);
  const done = { status: 'done', done_at: now, done_by: actor, assignee_id: null, assignee_note: null };
  await db.batch([
    guarded(op1, 'commented', { comment_id: c, body: note }, task.rev),
    db.prepare(`INSERT INTO todo_comment (id,task_id,author_id,body,created_at) SELECT ?,?,?,?,? WHERE EXISTS (SELECT 1 FROM todo_event WHERE op_id = ?)`)
      .bind(c, taskId, actor, note, now, op1),
    db.prepare(`UPDATE todo_task SET rev = rev + 1, updated_at = ?, updated_by = ? WHERE id = ? AND EXISTS (SELECT 1 FROM todo_event WHERE op_id = ?)`)
      .bind(now, actor, taskId, op1),
    guarded(op2, 'completed', done, task.rev + 1),
    db.prepare(`UPDATE todo_task SET status = 'done', done_at = ?, done_by = ?, assignee_id = NULL, assignee_note = NULL,
        rev = rev + 1, updated_at = ?, updated_by = ? WHERE id = ? AND EXISTS (SELECT 1 FROM todo_event WHERE op_id = ?)`)
      .bind(now, actor, now, actor, taskId, op2),
  ]);
  // a rev-őr csendben is elnyelheti (közbeeső írás): csak a tényleges állapot számít
  const after = await db.prepare('SELECT status FROM todo_task WHERE id = ?1').bind(taskId).first<{ status: string }>();
  return after?.status === 'done';
}

const ACTIVE = `('kiosztva', 'atadva', 'atveve', 'javit', 'ellenorzes')`;

/**
 * Az állapotgép vetülete a todo-ba (flotta-menedzser): a feladat a forrás tükre, nem a forrása.
 *   - a kiosztott menedzsernek (kiosztva … ellenőrzés) egy nyitott feladat, kiosztásonként új
 *     (idem_key `flotta:<incidens>:<átadások>:<menedzser>:<kiosztás ideje>`), hogy átadáskor a következő a saját labdájában lássa;
 *   - a régi feladat zárul (komment + kész), ha az incidens megoldódott, emberhez került,
 *     vagy másnak lett kiosztva.
 */
export async function syncTasks(db: D1Database, fleet: Fleet, at: Date) {
  let system: string | null = null;
  // előbb zárunk: a feladat gazdája ≠ a mostani kiosztott, vagy már nincs aktív állapotban
  const { results: stale } = await db.prepare(`${SELECT} WHERE i.fleet_id = ?1 AND i.todo_task_id IS NOT NULL
      AND (i.state NOT IN ${ACTIVE} OR i.assigned_principal_id IS NULL
        OR i.assigned_principal_id <> (SELECT owner_id FROM todo_task t WHERE t.id = i.todo_task_id))
      AND EXISTS (SELECT 1 FROM todo_task t WHERE t.id = i.todo_task_id AND t.status = 'open')`).bind(fleet.id).all<Row>()
    .catch(() => ({ results: [] as Row[] }));   // todo nélküli példány: nincs mit zárni
  for (const inc of stale) {
    const actor = system ??= await ensureSystemPrincipal(db);   // a rendszer zár, nem a menedzser nevében
    // a komment csak felsorolt értékekből (nem a tárolt resolve_note-ból)
    const note = inc.state === 'megoldva' ? closeNote(inc)
      : inc.state === 'ember-kell' ? '[flotta-ellenőrzés] Emberhez került; neked nincs vele több teendőd.'
      : '[flotta-ellenőrzés] Átadva a lánc következő menedzserének; neked nincs vele több teendőd.';
    const closed = await closeTask(db, actor, inc.todo_task_id!, note, at);
    // ha a rev-őr elnyelte (közbeeső írás), a feladat nyitva marad, és a következő kör újra próbálja
    if (closed) await event(db, inc.id, at, 'task_closed', { task_id: inc.todo_task_id, by_system: true, state: inc.state });
  }
  const { results } = await db.prepare(`${SELECT} WHERE i.fleet_id = ?1 AND i.state IN ${ACTIVE} AND i.assigned_principal_id IS NOT NULL
      AND i.check_key <> ?2 AND (i.todo_task_id IS NULL OR NOT EXISTS (SELECT 1 FROM todo_task t WHERE t.id = i.todo_task_id
        AND t.owner_id = i.assigned_principal_id AND t.status = 'open')) ORDER BY i.opened_at`).bind(fleet.id, OVERLOAD).all<Row>()
    .catch(() => ({ results: [] as Row[] }));
  let budget = results.length ? fleet.max_tasks_per_hour - await tasksLastHour(db, fleet.id, at) : 0;
  for (const inc of results) {
    if (budget <= 0) {   // óránkénti feladat-keret (AD-09): a többi vár, egy összegző incidens jelzi
      await overload(db, fleet, inc.box_id, `óránként több mint ${fleet.max_tasks_per_hour} új feladat; a többi incidens várakozik`, at);
      break;
    }
    system ??= await ensureSystemPrincipal(db);
    const task = await createTask(db, fleet, inc, inc.assigned_principal_id!, system, at);
    const set = await db.prepare('UPDATE flotta_incident SET todo_task_id = ?1 WHERE id = ?2 AND assigned_principal_id = ?3')
      .bind(task, inc.id, inc.assigned_principal_id).run();
    if (set.meta.changes) { await event(db, inc.id, at, 'task', { task_id: task, principal_id: inc.assigned_principal_id, handovers: inc.handovers }); budget--; }
  }
}
