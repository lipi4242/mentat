// lib/inbox.mjs — az inbox-konyvtar: tartos esemeny-naplo (events-*.jsonl),
// a bejovo kezbesitesi sorok (delivery-*.jsonl) es a retention-takaritas.
import { appendFileSync, mkdirSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { dirname, join } from "node:path";
import { makeRow, appendDelivery } from "./delivery-log.mjs";
import { writeHealth } from "./health.mjs";

// Tartos naplo: az offset CSAK e utan lephet. Ha az append elhasal (tele a
// lemez), DOBUNK — a poll-ciklus nem lepteti az offsetet, az update ujra
// lejon. Inkabb dolgozzuk fel ketszer, mint hogy elvesszen. A
// `last_event_error` health-mezo teszi utolag is lathatova ezt az allapotot.
export function appendEvent(inboxDir, healthFile, upd) {
  const path = join(inboxDir, `events-${new Date().toISOString().slice(0, 10)}.jsonl`);
  try {
    mkdirSync(dirname(path), { recursive: true });
    appendFileSync(path, JSON.stringify(upd) + "\n");
  } catch (e) {
    writeHealth(healthFile, { last_event_error: Date.now() });
    throw new Error(`event append FAILED (offset nem lép): ${e.message}`);
  }
}

// Bejovo kezbesitesi sor (docs/delivery-log.md, type:"inbound"): SIKERES
// kezbesites/enqueue UTAN hivando. Best-effort: a tartossag az events-naplo
// dolga; egy iras-hiba SOSEM dobhat tovabb (az offset-szemantika serulne),
// csak a health.json `last_delivery_log_error` mezoje jelzi.
export function createInboundLogger({ inboxDir, healthFile, log = () => {} }) {
  return function logInbound(fields) {
    try {
      const res = appendDelivery(inboxDir, makeRow({ type: "inbound", ...fields }));
      if (!res.ok) {
        log("kezbesitesi naplo iras hiba (nema, a fo folyam megy):", res.error);
        writeHealth(healthFile, { last_delivery_log_error: Date.now() });
      }
    } catch (e) {
      log("kezbesitesi naplo iras hiba (nema, a fo folyam megy):", e.message);
      writeHealth(healthFile, { last_delivery_log_error: Date.now() });
    }
  };
}

export function pruneInbox(dir, days, now = Date.now()) {
  const cutoff = now - days * 24 * 60 * 60 * 1000;
  let removed = 0;
  const walk = (d) => {
    let entries;
    try {
      entries = readdirSync(d, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else {
        try {
          if (statSync(p).mtimeMs < cutoff) { unlinkSync(p); removed++; }
        } catch {
          /* verseny a torlessel — nem baj */
        }
      }
    }
  };
  walk(dir);
  return removed;
}
