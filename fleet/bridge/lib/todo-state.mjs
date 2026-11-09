// lib/todo-state.mjs — a todo-ebresztes tartos allapota (<state>/telegram-state/todo-state.json).
//
//   key      "<api> <handle>": masik peldanyon/handle-on a seq mast jelent, ott ujrakezdunk
//   me       { id, handle } a /me-bol (a sajat irasok szuresehez)
//   cursor   az utolso FELDOLGOZOTT esemeny seq-je (null: meg nem indult -> a multat atugorjuk)
//   buffer   a kesz, de meg ki nem kuldott ebresztes-tetelek (osszevonasra varnak)
//   wakes    a kikuldott ebresztesek: { id, at, tasks, refs, deadline, late?, latency_ms }
//   runaway  lib/todo-runaway.mjs allapota
// A cursor es a buffer EGY fajlban, egy atomikus irassal lep: lepett kurzor mellett nem veszhet el
// ki nem kuldott tetel. Az iras STRIKT (dob) — a hivo nem lepteti tovabb az allapotot.
import { loadJsonQuarantine, saveJsonStrict } from "./jsonfile.mjs";
import { logNotice } from "./notice.mjs";

export const WAKE_KEEP_MS = 24 * 3600_000;
const fresh = (key) => ({ key, me: null, cursor: null, buffer: [], wakes: [], runaway: {} });

export function loadTodoState(file, key, onCorrupt) {
  const s = loadJsonQuarantine(file, null, onCorrupt);
  if (!s || typeof s !== "object" || s.key !== key) return fresh(key);
  return { ...fresh(key), ...s, buffer: Array.isArray(s.buffer) ? s.buffer : [],
    wakes: Array.isArray(s.wakes) ? s.wakes : [], runaway: s.runaway && typeof s.runaway === "object" ? s.runaway : {} };
}

export const saveTodoState = (file, st) => saveJsonStrict(file, st);

// Egy tetel a pufferbe: ugyanaz a tetel egy sorrá vonodik (igek es szerzok unioja, a legnagyobb seq).
export function addEntry(buffer, e) {
  const old = buffer.find((x) => x.task_id === e.task_id);
  if (!old) { buffer.push(e); return; }
  const uniq = (a, b) => [...new Set([...String(a).split(", "), ...String(b).split(", ")].filter(Boolean))].join(", ");
  Object.assign(old, { seq: Math.max(old.seq, e.seq), verb: uniq(old.verb, e.verb), by: uniq(old.by, e.by),
    title: e.title || old.title, at: Math.min(old.at, e.at) });
}

// Nyugta-konyveles: a sajat iras egy ebresztes tetelein (a kivalto esemenyek UTAN, seq > wake.id)
// = feldolgozva; a hatarido utan `late` (feldolgozatlan), de 24 oraig kesve is nyugtazhato.
// A sajat iras nem mindig jon vissza a /changes-ben (ha az agens se nem gazda, se nem felelos, a
// sajat kommentjenek nem cimzettje): a hatarido elott ezert `verify(w)` meg a tetelt is megnezi.
export function createWakeBook({ st, logDir, now = Date.now, verify = async () => false }) {
  const notice = (event, w, extra = {}) => logNotice(logDir, event, { chat_id: "todo", msg_id: String(w.id),
    detail: w.refs.join(", ").slice(0, 300), ...extra });
  function handled(taskId, seq) {
    let n = 0;
    st.wakes = st.wakes.filter((w) => {
      if (!(w.tasks.includes(taskId) && seq > w.id)) return true;
      notice("todo_wake_handled", w, { ...(w.late ? { kind: "kesve" } : {}) });
      n++;
      return false;
    });
    return n;
  }
  async function sweep() {
    const t = now();
    for (const w of [...st.wakes]) {
      if (w.late || t < w.deadline) continue;
      let ok = false;
      try { ok = await verify(w); } catch { ok = false; } // nem mérhető: marad a feldolgozatlan jel
      if (ok) {
        st.wakes = st.wakes.filter((x) => x !== w);
        notice("todo_wake_handled", w, { kind: "tetelen" });
      } else { w.late = true; notice("todo_wake_unhandled", w); }
    }
    st.wakes = st.wakes.filter((w) => t - w.at < WAKE_KEEP_MS);
  }
  const unhandled = () => st.wakes.filter((w) => w.late).length;
  return { handled, sweep, unhandled };
}
