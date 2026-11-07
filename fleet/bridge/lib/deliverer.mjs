// lib/deliverer.mjs — tmux-kezbesites pending-vedohaloval.
//
// A `tmux send-keys` sikeres visszaterese NEM kezbesites-garancia, de a
// sikertelen inject biztosan nem az: az ilyen sor lemezes pending-sorba kerul,
// es PENDING_RETRY_MS-enkent ujraprobaljuk. KORLATOS at-least-once: a sor
// `maxPending` melysegnel a LEGREGEBBIT dobja, hangos riasztassal — a
// visszajatszas forrasa ilyenkor is az events-*.jsonl.
import { saveJsonStrict, loadJsonQuarantine } from "./jsonfile.mjs";
import { capPending } from "./pending.mjs";
import { injectLine } from "./inject.mjs";
import { writeHealth } from "./health.mjs";

export function oldestPendingAgeMs(items, now = Date.now()) {
  if (!items.length) return 0;
  return now - Math.min(...items.map((p) => p.ts || now));
}

export function createDeliverer({
  session, pendingFile, maxPending, pendingAlertMs, healthFile, label,
  alert = async () => {}, log = () => {}, onCorrupt = () => {}, inject = injectLine,
  beforeInject = () => {}, onInjected = () => {},
}) {
  let pending = loadJsonQuarantine(pendingFile, [], onCorrupt);
  if (!Array.isArray(pending)) pending = [];
  let pendingAlerted = false;
  // Melyseg-sapka jelzese: EGYSZER a folyamat elete alatt (ne zudits riasztas-aradatot).
  let dropAlerted = false;
  // Az utolso sikertelen inject oka: a riasztas megnevezi (pl. engedelykero ablak).
  let lastError = "";

  // Horgok (3.2 nyugta): beforeInject az inject ELOTT, onInjected csak SIKER utan —
  // kozvetlen es pending-uton egyarant. Hibajuk naplo, a kezbesitest nem allitja meg.
  const hook = (fn, line) => {
    try { fn(line); } catch (e) { log("inject-horog hiba:", e.message); }
  };
  const tryInject = (line) => {
    hook(beforeInject, line);
    const res = inject(session, line);
    if (!res.ok) { log(res.error); lastError = res.dialog ? res.error : ""; }
    else hook(onInjected, line);
    return res.ok;
  };

  function pushPending(line) {
    const { items, dropped } = capPending(pending, { line, ts: Date.now() }, maxPending);
    pending = items;
    // STRIKT: a pending az egyetlen tartos masolat egy kezbesitetlen sorrol. Ha
    // nem irodott ki, dobunk — a poll-ciklus igy nem lepteti az offsetet.
    saveJsonStrict(pendingFile, pending);
    if (dropped && !dropAlerted) {
      dropAlerted = true;
      alert(`pending-sor tele (${maxPending}) — a legrégebbi üzenetek kiesnek`).catch(() => {});
    }
  }

  function deliver(line) {
    // Sorrend-tartas: ha mar all a sor, moge allunk, nem ele vagunk.
    if (pending.length || !tryInject(line)) return pushPending(line);
    log("injected:", line.slice(0, 200));
    writeHealth(healthFile, { last_delivered: Date.now() });
  }

  async function retryPending() {
    while (pending.length) {
      if (!tryInject(pending[0].line)) break;
      log("pending injected:", pending[0].line.slice(0, 160));
      pending.shift();
      try {
        saveJsonStrict(pendingFile, pending);
      } catch (e) {
        // A torles nem ment lemezre: restart utan ez a sor ujra elojon.
        // Duplikacio > vesztes — megallunk, a kovetkezo retry ujraprobalja.
        log("pending mentés hiba (az elem újra elő fog jönni):", e.message);
        break;
      }
    }
    if (!pending.length) {
      if (pendingAlerted) {
        pendingAlerted = false;
        await alert(`a felgyűlt üzeneteket átadtam ${label}nak, a sor üres.`);
      }
      return;
    }
    if (!pendingAlerted && oldestPendingAgeMs(pending) > pendingAlertMs) {
      pendingAlerted = true;
      await alert(
        `${pending.length} üzenetet nem tudok átadni ${label}nak (${lastError || "a tmux session nem fogad"}). ` +
        `Az üzenetek megvannak, sorban állnak — nézzetek rá a ${label} szolgáltatásra.`,
      );
    }
  }

  return { deliver, retryPending, depth: () => pending.length };
}
