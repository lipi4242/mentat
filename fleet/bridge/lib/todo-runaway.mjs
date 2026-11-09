// lib/todo-runaway.mjs — a nyilvanvalo elszabadulas fekje (AC 4).
//
// A tulajdonos kifejezett kerese: az agensek beszelgethetnek egymassal egy tetel kommentjeiben, ezt
// NEM fojtjuk el — nincs orankenti plafon. Csak a nyilvanvalo elszabadulas lassul: ugyanazon a
// tetelen rovid idon belul (windowMs) sok (limit) TARTALOM NELKULI komment, legalabb ket szerzotol
// (oda-vissza). Ilyenkor a tetel ebresztese slowMs-ig visszatartva gyulik (egy ebresztes a vegen),
// es MINDIG jelzes megy (onSignal): naplo-notice, csoport-riasztas, health. Semmi nem esik ki.
// A tartalmas beszelgetes (barmilyen hosszu) sosem lassul.
import { contentFree, diffOf } from "./todo-relevance.mjs";

export const WINDOW_MS = 10 * 60_000;
export const LIMIT = 8;
export const SLOW_MS = 5 * 60_000;

// state: { [task_id]: { hits: [{ at, actor }], slow_until } } — a hivo tartosan menti.
export function createRunaway({ state = {}, windowMs = WINDOW_MS, limit = LIMIT, slowMs = SLOW_MS,
  onSignal = () => {} } = {}) {
  // Egy komment-esemeny (sajat is: az oda-vissza ket oldala) -> szamlalas.
  function observe(ev, t) {
    if (ev?.kind !== "commented" || !ev.task_id) return;
    const s = state[ev.task_id] || (state[ev.task_id] = { hits: [], slow_until: 0 });
    s.hits = s.hits.filter((h) => t - h.at < windowMs);
    if (!contentFree(diffOf(ev).body)) return; // a tartalmas komment nem szamit
    s.hits.push({ at: t, actor: ev.actor_id });
    const actors = new Set(s.hits.map((h) => h.actor)).size;
    if (s.hits.length >= limit && actors >= 2 && t >= s.slow_until) {
      s.slow_until = t + slowMs;
      try { onSignal({ task_id: ev.task_id, count: s.hits.length, until: s.slow_until }); } catch { /* jelzes-hiba nem allit meg */ }
    }
  }
  const holdUntil = (taskId) => state[taskId]?.slow_until || 0;
  const slowed = (t) => Object.entries(state).filter(([, s]) => s.slow_until > t).map(([id]) => id);
  // A regi, csendes bejegyzesek takaritasa (a state ne nojon korlatlanul).
  function prune(t) {
    for (const [id, s] of Object.entries(state)) {
      s.hits = s.hits.filter((h) => t - h.at < windowMs);
      if (!s.hits.length && s.slow_until <= t) delete state[id];
    }
  }
  return { observe, holdUntil, slowed, prune, state };
}
