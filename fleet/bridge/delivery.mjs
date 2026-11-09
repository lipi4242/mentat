#!/usr/bin/env node
// delivery.mjs — "kiment-e a valasz?" a kezbesitesi naplobol (docs/delivery-log.md).
//   node ~/.config/<agens>/sub-etha/delivery.mjs [--day YYYY-MM-DD] [--json]
// Kimenet: bejovo-szam, kuldesek statusz szerint (a darabolt kuldes EGY), notice-ok
// esemenyenkent, megvalaszolatlan bejovok,
// bizonytalan (unknown) kuldesek. Exit: 0 rendben, 2 van megvalaszolatlan
// vagy unknown, 1 hasznalati hiba / ismeretlen naplo-hely.
import { fileURLToPath } from "node:url";
import { readDay, summarize, resolveLogDir, dayOf } from "./lib/delivery-log.mjs";

const clip = (s, n = 60) => {
  const t = String(s ?? "").replace(/\s+/g, " ");
  return t.length > n ? `${t.slice(0, n)}…` : t;
};

export function report(sum, day) {
  const c = sum.counts;
  const out = [`${day}: ${sum.inbound} bejövő; küldés: ${c.confirmed} confirmed, ${c.failed} failed, ${c.unknown} unknown`];
  // Fix sorrend a negy ismert esemenyre, utana a tobbi.
  const known = ["inbound_unconfirmed", "todo_wake_unhandled", "todo_runaway", "webhook_failed", "deprecated_flag",
    "inbound_confirmed", "todo_wake_handled"];
  const ev = Object.keys(sum.notices || {}).sort((a, b) => (known.indexOf(a) + 1 || 99) - (known.indexOf(b) + 1 || 99));
  if (ev.length) out.push(`notice: ${ev.map((e) => `${e} ${sum.notices[e]}`).join(", ")}`);
  for (const r of sum.unanswered) out.push(`MEGVÁLASZOLATLAN chat=${r.chat_id} msg=${r.msg_id} ${r.from ?? ""}: ${clip(r.text)}`);
  for (const s of sum.uncertain) {
    const why = s.has_outcome ? s.error || "timeout" : "a küldő folyamat a kérés közben leállt";
    out.push(`UNKNOWN chat=${s.chat_id} reply_to=${s.reply_to ?? "-"} (${why}): ${clip(s.text)}`);
  }
  return out.join("\n");
}

export function main(argv = process.argv.slice(2), env = process.env) {
  let day = dayOf();
  let json = false;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--day" && /^\d{4}-\d{2}-\d{2}$/.test(argv[i + 1] || "")) day = argv[++i];
    else if (argv[i] === "--json") json = true;
    else { console.error("usage: delivery.mjs [--day YYYY-MM-DD] [--json]"); return 1; }
  }
  const dir = resolveLogDir(env, fileURLToPath(import.meta.url));
  if (!dir) { console.error("kezbesitesi naplo helye ismeretlen (BRIDGE_STATE_DIR?)"); return 1; }
  const sum = summarize(readDay(dir, day));
  console.log(json ? JSON.stringify({ day, ...sum }) : report(sum, day));
  return sum.unanswered.length || sum.uncertain.length ? 2 : 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) process.exit(main());
