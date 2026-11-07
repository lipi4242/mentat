// lib/delivery-summary.mjs — napi osszkep a kezbesitesi naplobol (docs/delivery-log.md).
// Egy valasz = egy intent-csoport: a darabolt kuldes (`part` "k/n", lib/send-run.mjs)
// darabjai EGY kuldeskent szamitanak. A notice-ok esemenyenkent szamolva.
import { resolveSends } from "./delivery-log.mjs";

const pidOf = (id) => String(id ?? "").split("-")[1] ?? "";
const partOf = (p) => {
  const m = /^(\d+)\/(\d+)$/.exec(String(p ?? ""));
  return m ? { k: Number(m[1]), n: Number(m[2]) } : null;
};

// A csoport statusza: az elso nem-confirmed darabe (a send-run ott megall);
// ha minden naplozott darab confirmed, de kevesebb, mint n: failed (a tobbi el sem indult).
function finalize(g) {
  const bad = g.items.find((s) => s.status !== "confirmed");
  const last = g.items[g.items.length - 1];
  const head = g.items[0];
  const status = bad ? bad.status : g.items.length < g.n ? "failed" : "confirmed";
  const error = bad ? bad.error : status === "failed" ? `csak ${g.items.length}/${g.n} darab` : undefined;
  return { ...head, status, has_outcome: bad ? bad.has_outcome : last.has_outcome, error,
    parts: g.items.length, message_id: last.message_id };
}

export function groupSends(sends) {
  const groups = [];
  const open = new Map(); // pid:chat:n -> { k-ra varo csoport }
  for (const s of sends) {
    const p = partOf(s.part);
    const key = p ? `${pidOf(s.send_id)}:${s.chat_id}:${p.n}` : null;
    const g = key && p.k > 1 ? open.get(key) : null;
    if (g && g.next === p.k) {
      g.items.push(s); g.next++;
      if (g.next > g.n) open.delete(key);
      continue;
    }
    const ng = { items: [s], n: p ? p.n : 1, next: p ? p.k + 1 : 2 };
    groups.push(ng);
    if (p && p.n > 1) open.set(key, ng);
  }
  return groups.map(finalize);
}

// Megvalaszolt egy bejovo, ha van hozza confirmed `message` valasz ugyanabban a
// chatben, reply_to = msg_id. A reakcio nyugta, nem valasz; a bejovo reakcio nem kerdes.
export function summarize(rows) {
  const sends = groupSends(resolveSends(rows));
  const counts = { confirmed: 0, failed: 0, unknown: 0 };
  for (const s of sends) counts[s.status]++;
  const notices = {};
  for (const r of rows) if (r.type === "notice" && r.event) notices[r.event] = (notices[r.event] || 0) + 1;
  const answered = new Set(sends
    .filter((s) => s.action === "message" && s.status === "confirmed" && s.reply_to != null)
    .map((s) => `${s.chat_id}:${s.reply_to}`));
  const inbound = rows.filter((r) => r.type === "inbound" && r.kind !== "reaction" && r.msg_id != null);
  const seen = new Set();
  const unanswered = [];
  for (const r of inbound) {
    const key = `${r.chat_id}:${r.msg_id}`;
    if (seen.has(key)) continue; // a szerkesztes ugyanaz az uzenet
    seen.add(key);
    if (!answered.has(key)) unanswered.push(r);
  }
  return { inbound: seen.size, counts, notices, sends, unanswered,
    uncertain: sends.filter((s) => s.status === "unknown") };
}
