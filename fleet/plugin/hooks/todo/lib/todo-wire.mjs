// lib/todo-wire.mjs — a todo-ebresztes bekotese a hidba.
// KI (nincs todo a boxon / BRIDGE_TODO=off / hasznalhatatlan token): ures drot, a health
// `todo_wake` mezoje mondja meg, miert (a flotta-ellenorzes ebbol mer, fleet/src/fleet/kepesseg.py).
// Be: pollMs-enkent egy kor (lib/todo-poll.mjs), egyszerre egy; a kor hibaja sosem dont hidat.
import { readFileSync } from "node:fs";
import { writeHealth } from "./health.mjs";
import { createTodoApi } from "./todo-api.mjs";
import { createTodoPoller } from "./todo-poll.mjs";
import { createRunaway } from "./todo-runaway.mjs";
import { createWakeBook, loadTodoState } from "./todo-state.mjs";
import { logNotice } from "./notice.mjs";
import { safeId } from "./todo-safe.mjs";

const VERSION = (() => {
  try { return readFileSync(new URL("../VERSION", import.meta.url), "utf8").trim(); } catch { return "0"; }
})();
const OFF = { summary: "todo=off", start: () => {}, stop: () => {}, tick: async () => null, depth: () => 0 };

export function createTodoWire(CFG, { deliver, logInbound, log = () => {}, alert = async () => {}, onCorrupt,
  fetchFn, now = Date.now, timeoutMs } = {}) {
  const cfg = CFG.todo;
  // stamp:false: a todo-mezok nem frissitik a `written_at`-ot (az a Telegram-poller eletjele marad).
  const health = (f) => writeHealth(CFG.healthFile, f, { stamp: false });
  if (!cfg?.enabled) {
    if (cfg?.reason) console.error(`[bridge] TODO-ÉBRESZTÉS KI: ${cfg.reason}`);
    health({ todo_wake: cfg?.reason ? `off: ${cfg.reason}` : "off" });
    return OFF;
  }
  const st = loadTodoState(cfg.stateFile, `${cfg.api} ${cfg.handle}`, onCorrupt);
  const api = createTodoApi({ api: cfg.api, tokenFile: cfg.tokenFile, version: VERSION, ...(fetchFn ? { fetchFn } : {}),
    ...(timeoutMs ? { timeoutMs } : {}) });
  // A hatarido elotti utolso nezes: van-e a kivalto esemenyek utan sajat komment vagy modositas a tetelen.
  const verify = async (w) => {
    for (const id of w.tasks) {
      const t = await api.task(id).catch((e) => { if (e?.status === 404) return null; throw e; });
      const mine = (by, at) => by === st.me?.id && Date.parse(at) >= (w.ev_at ?? w.at); // >=: ugyanabban a ms-ban is utana jott (a kivalto nem sajat)
      if (t && (mine(t.updated_by, t.updated_at) || (t.comments || []).some((c) => mine(c.author_id, c.created_at)))) return true;
    }
    return false;
  };
  const book = createWakeBook({ st, logDir: CFG.inboxDir, now, verify });
  // Elszabadulas: soha nem nema — notice a naploba, egy sor a csoportnak, health-mezo.
  const runaway = createRunaway({ state: st.runaway, onSignal: ({ task_id: raw, count, until }) => {
    const task_id = safeId(raw); // a desktopon ez is a kontextusba megy: csak zart alak
    const mins = Math.round((until - now()) / 60_000);
    logNotice(CFG.inboxDir, "todo_runaway", { chat_id: "todo", detail: `task=${task_id} ${count} komment` });
    log(`todo-ébresztés: elszabadulás-fék task=${task_id} (${count} tartalom nélküli komment) — ${mins} percig gyűjtve`);
    alert(`todo: a(z) task:${task_id} tételen ${count} tartalom nélküli oda-vissza komment ment rövid idő alatt — `
      + `az ébresztése ${mins} percig gyűjtve megy (semmi nem vész el). Nézzetek rá, nem akadt-e körbe két ágens.`).catch(() => {});
  } });
  const poller = createTodoPoller({ cfg, api, st, book, runaway, deliver, logInbound, health, log, now });
  health({ todo_wake: "on", todo_poll_ms: cfg.pollMs });
  let timer = null;
  let running = null;
  const tick = () => {
    if (running) return running;
    running = poller.tick().catch((e) => { log("todo-kör hiba:", e.message); return null; })
      .finally(() => { running = null; });
    return running;
  };
  return {
    summary: `todo=on handle=${cfg.handle} poll=${Math.round(cfg.pollMs / 1000)}s`,
    tick,
    start: () => {
      if (timer) return;
      tick();
      timer = setInterval(tick, cfg.pollMs);
      timer.unref?.();
    },
    stop: () => { clearInterval(timer); timer = null; },
    depth: () => st.buffer.length,
    state: st,
  };
}
