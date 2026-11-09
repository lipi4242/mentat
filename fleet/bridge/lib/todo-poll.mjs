// lib/todo-poll.mjs — egy todo-poll kor: /changes a kurzor utan, szures, puffer, ebresztes.
//
// Sorrend egy korben: (1) a kurzor utani esemenyek oldalanként; mindegyik: runaway-szamlalo, sajat iras
// -> nyugta, kulonben releváns-e (lib/todo-relevance.mjs) -> puffer; az oldal vegen a kurzor ES a
// puffer egy irassal lemezre. (2) Ha a puffer kesz (ebben a korben nem jott uj tetel, vagy a legregebbi
// coalesceMs ota var), EGY sor megy a deliver-re — ugyanaz az ut, mint a Telegram-sore (foglalt agensnel
// sorba all, sikertelen injectnel pending-sor, nyugta). (3) Lejart ebresztesek: feldolgozatlan-jelzes.
// Elso indulas (nincs kurzor): a mult atugorva, ebresztes nelkul (azt az orankenti tick kezeli).
import { NEEDS_TASK, classify, isOwn } from "./todo-relevance.mjs";
import { addEntry, saveTodoState } from "./todo-state.mjs";
import { buildTodoLine, wakeId } from "./todo-lines.mjs";

export const PAGE = 100;
const SKIP_PAGE = 500;

export function createTodoPoller({ cfg, api, st, book, runaway, deliver, logInbound = () => {}, health = () => {},
  log = () => {}, now = Date.now }) {
  const save = () => saveTodoState(cfg.stateFile, st);
  let names = new Map();
  let namesAt = 0;
  async function who(id) {
    if (!names.has(id) && now() - namesAt > 10 * 60_000) {
      namesAt = now();
      const rows = await api.principals().catch(() => []);
      // Csak a handle (zart alak): a megjelenitett nev szabad szoveg, a sorba nem kerul.
      if (Array.isArray(rows)) names = new Map(rows.map((p) => [p.id, p.handle]));
    }
    return names.get(id) || "?";
  }
  const fetchOr404 = (p) => p.catch((e) => { if (e?.status === 404) return null; throw e; });

  async function skipBacklog() {
    let since = 0;
    for (;;) {
      const rows = await api.changes(cfg.handle, since, SKIP_PAGE);
      if (!Array.isArray(rows)) throw new Error("todo API: a /changes nem lista");
      if (rows.length) since = rows[rows.length - 1].seq;
      if (rows.length < SKIP_PAGE) return since;
    }
  }

  async function onEvent(ev, cache, t) {
    runaway.observe(ev, Date.parse(ev.at) || t);
    if (isOwn(ev, st.me)) { if (ev.task_id) book.handled(ev.task_id, ev.seq); return 0; }
    if (!NEEDS_TASK.has(ev.kind) || !ev.task_id) return 0;
    if (!cache.has(ev.task_id)) cache.set(ev.task_id, await fetchOr404(api.task(ev.task_id)));
    const task = cache.get(ev.task_id);
    const c = classify(ev, st.me, task);
    if (!c) return 0;
    let ref = `task:${ev.task_id}`;
    if (task?.kind === "item") ref = (await fetchOr404(api.item(ev.task_id)))?.key || ref;
    addEntry(st.buffer, { seq: ev.seq, task_id: ev.task_id, ref, verb: c.verb, by: await who(ev.actor_id),
      title: task?.title || "", at: Date.parse(ev.at) || t, found_at: t });
    return 1;
  }

  async function pull(t) {
    if (!st.me) {
      const me = await api.me();
      if (!me?.id) throw new Error("todo API: a /me nem principal");
      st.me = { id: me.id, handle: me.handle || cfg.handle };
    }
    if (st.cursor == null) {
      st.cursor = await skipBacklog();
      save();
      log(`todo-ébresztés: első indulás, a korábbi események átugorva (kurzor=${st.cursor})`);
      return 0;
    }
    let added = 0;
    const cache = new Map();
    try {
      for (;;) {
        const rows = await api.changes(cfg.handle, st.cursor, PAGE);
        if (!Array.isArray(rows) || rows.some((r) => !Number.isSafeInteger(r?.seq))) throw new Error("todo API: a /changes nem eseménylista");
        for (const ev of rows) { added += await onEvent(ev, cache, t); st.cursor = ev.seq; }
        if (rows.length < PAGE) break;
      }
    } finally {
      save(); // a felig feldolgozott oldal is: a kurzor csak a kesz esemenyekig lepett
    }
    return added;
  }

  function flush(t, added) {
    const ready = st.buffer.filter((e) => runaway.holdUntil(e.task_id) <= t);
    if (!ready.length) return null;
    const oldest = Math.min(...ready.map((e) => e.found_at));
    if (added && t - oldest < cfg.coalesceMs) return null; // meg jon: varunk, egy ebresztes lesz
    const slowed = ready.filter((e) => e.slowed).map((e) => e.ref);
    const line = buildTodoLine(ready, { slowed });
    deliver(line); // dob, ha a pending-sor sem irhato: a puffer marad, a kovetkezo kor ujra probalja
    const id = wakeId(ready);
    const latency = t - Math.min(...ready.map((e) => e.at));
    st.buffer = st.buffer.filter((e) => !ready.includes(e));
    st.wakes.push({ id, at: t, ev_at: Math.max(...ready.map((e) => e.at)), tasks: [...new Set(ready.map((e) => e.task_id))],
      refs: ready.map((e) => e.ref), deadline: t + cfg.handledMs, latency_ms: latency });
    try { save(); } catch (e) { log("todo-állapot mentése az ébresztés után sikertelen (duplikált ébresztés lehet):", e.message); }
    logInbound({ chat_id: "todo", msg_id: String(id), kind: "todo", from: [...new Set(ready.map((e) => e.by))].join(", "), text: line });
    health({ todo_last_wake_at: t, todo_last_wake_latency_ms: latency });
    return line;
  }

  async function tick() {
    const t = now();
    let added = 0;
    try {
      added = await pull(t);
      health({ todo_last_poll_ok: now(), todo_last_error: null });
    } catch (e) {
      log("todo-poll hiba:", e.message);
      health({ todo_last_poll_error: now(), todo_last_error: String(e.message).slice(0, 200) });
    }
    for (const id of runaway.slowed(t)) for (const e of st.buffer) if (e.task_id === id) e.slowed = true;
    let line = null;
    try { line = flush(t, added); } catch (e) { log("todo-ébresztés kézbesítési hiba:", e.message); }
    try { await book.sweep(); } catch (e) { log("todo-nyugta hiba:", e.message); }
    runaway.prune(t);
    try { save(); } catch (e) { log("todo-állapot mentési hiba:", e.message); }
    health({ todo_buffered: st.buffer.length, todo_unhandled: book.unhandled(),
      todo_runaway: runaway.slowed(t).length });
    return { added, line };
  }
  return { tick, flush };
}
