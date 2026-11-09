// lib/delivery-log.mjs — a kezbesitesi naplo (sema: docs/delivery-log.md).
//
// Miert kell: a Telegram SOSEM adja vissza egy bot sajat uzeneteit, tehat
// "kiment-e a valasz?" kerdesre csak a sajat naplonk felel. Negy sortipus:
//   inbound — a hid irja, a bejovo uzenet kezbesitese/sorba allitasa utan;
//   intent  — a send.mjs irja, MIELOTT a Telegram-hivas elindul;
//   outcome — a send.mjs irja a hivas utan: confirmed | failed | unknown;
//   notice  — esemeny (lib/notice.mjs), pl. deprecated_flag; nem kuldes.
// Egy intent kimenet nelkul = unknown: a folyamat a keres utan halt meg. Ezt
// a szandek-sor elore irasa garantalja — a naplo nem hallgathat el egy kuldest.
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { MAX_ROW_BYTES, capField, clampEntryText, enforceRowLimit } from "./clamp.mjs";

export const LOG_VERSION = 1;
export const TYPES = ["inbound", "intent", "outcome", "notice"];
export const STATUSES = ["confirmed", "failed", "unknown"];
const OPTIONAL = ["msg_id", "kind", "from", "from_id", "reply_to", "target_msg_id",
  "action", "send_id", "status", "message_id", "error", "event", "detail", "part", "target", "media"];

let seq = 0;

export const dayOf = (ts = Date.now()) => new Date(ts).toISOString().slice(0, 10);
export const logPath = (dir, ts = Date.now()) => join(dir, `delivery-${dayOf(ts)}.jsonl`);

export function makeRow(fields) {
  const { type, ts = Date.now(), chat_id = null, text } = fields;
  if (!TYPES.includes(type)) throw new Error(`delivery row: ismeretlen type: ${type}`);
  if (type === "outcome") {
    if (!fields.send_id) throw new Error("delivery row: outcome send_id nelkul");
    if (!STATUSES.includes(fields.status))
      throw new Error(`delivery row: ismeretlen status: ${fields.status}`);
  }
  if (type === "notice" && !fields.event) throw new Error("delivery row: notice event nelkul");
  const row = { v: LOG_VERSION, id: `${ts}-${process.pid}-${seq++}`, ts, type,
    chat_id: capField(chat_id == null ? null : String(chat_id)) };
  for (const k of OPTIONAL) if (fields[k] !== undefined) row[k] = capField(fields[k]);
  if (typeof text === "string") row.text = clampEntryText(row, text.slice(0, 4096), MAX_ROW_BYTES);
  return enforceRowLimit(row, MAX_ROW_BYTES, `type=${type}`);
}

// Egy appendFileSync hivas (O_APPEND, <4 KB): tobb iro (hid + send.mjs-ek)
// mellett is egesz sorok. Egyszeri retry, SOSEM dob — a hivo jelez tovabb.
export function appendDelivery(dir, row, now = Date.now()) {
  const path = logPath(dir, now);
  const line = JSON.stringify(row) + "\n";
  let error = "";
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      mkdirSync(dirname(path), { recursive: true });
      appendFileSync(path, line);
      return { ok: true, path };
    } catch (e) {
      error = e.message;
    }
  }
  return { ok: false, error };
}

// Egy nap sorai. A hianyzo fajl ures nap; a parszolhatatlan (pl. egy
// folyamat-halal altal csonkitott) sort atugorjuk, nem dobunk.
export function readDay(dir, day) {
  let raw;
  try {
    raw = readFileSync(join(dir, `delivery-${day}.jsonl`), "utf8");
  } catch {
    return [];
  }
  const rows = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    try { rows.push(JSON.parse(line)); } catch { /* csonka sor */ }
  }
  return rows;
}

// Minden intent egy kuldes; a statusza az utolso hozza tartozo outcome-e,
// ennek hianyaban unknown (has_outcome:false — a folyamat a keres kozben halt meg).
export function resolveSends(rows) {
  const outcomes = new Map();
  for (const r of rows) if (r.type === "outcome") outcomes.set(r.send_id, r);
  return rows.filter((r) => r.type === "intent").map((r) => {
    const o = outcomes.get(r.id);
    return {
      send_id: r.id, ts: r.ts, chat_id: r.chat_id, action: r.action,
      reply_to: r.reply_to, target_msg_id: r.target_msg_id, text: r.text,
      status: o ? o.status : "unknown", has_outcome: Boolean(o),
      message_id: o?.message_id, error: o?.error, part: r.part,
    };
  });
}

// Napi osszkep (valasz = intent-csoport, notice-ok esemenyenkent): lib/delivery-summary.mjs.
export { summarize, groupSends } from "./delivery-summary.mjs";

// Hova ir a send.mjs: env (ugyanaz a dontes, mint a hid lib/config.mjs-e),
// kulonben a telepitesi hely (<state>/sub-etha/send.mjs -> <state>/telegram-inbox).
export function resolveLogDir(env, scriptPath) {
  if (env.BRIDGE_INBOX_DIR) return env.BRIDGE_INBOX_DIR;
  if (env.BRIDGE_STATE_DIR) return join(env.BRIDGE_STATE_DIR, "telegram-inbox");
  const here = dirname(scriptPath || "");
  if (basename(here) === "sub-etha") return join(dirname(here), "telegram-inbox");
  return null;
}
