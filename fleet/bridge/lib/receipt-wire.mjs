// lib/receipt-wire.mjs — az erkezes-nyugta (3.2) bekotese a hidba.
// KI (BRIDGE_RECEIPT != "1"): ures horgok, semmi nem irodik — a hid bitre a regi.
import { createReceipts } from "./receipt.mjs";
import { logNotice } from "./notice.mjs";

// A ⚠️ NEM szerepel a Telegram ReactionTypeEmoji engedett listajan — a
// setMessageReaction elutasitana. A 😨 engedett, es ugyanazt jelzi.
export const UNCONFIRMED_REACTION = "😨";

export function createReceiptWire(CFG, { tg, alert = async () => {}, log = () => {}, onCorrupt, now,
  windowMs, checkMs = 15_000 } = {}) {
  if (!CFG.receipt) {
    return { hooks: {}, bind: () => {}, start: () => {}, stop: () => {}, check: () => {}, depth: () => 0 };
  }
  // A deliverer es a receipts kolcsonosen hivatkoznak: a reinject kesleltetett referencia.
  let delivery = null;
  const react = (chat_id, message_id) =>
    Promise.resolve()
      .then(() => tg("setMessageReaction", { chat_id, message_id, reaction: [{ type: "emoji", emoji: UNCONFIRMED_REACTION }] }))
      .catch((e) => log("nyugta-reakció hiba:", e.message));
  let noTranscriptAlerted = false;
  const say = (t) => Promise.resolve().then(() => alert(t)).catch((e) => log("nyugta-riasztás hiba:", e.message));
  let staleIds = [];
  const onCheckEnd = () => {
    if (!staleIds.length) return;
    const ids = staleIds; staleIds = [];
    say(`${ids.length} üzenet ellenőrizetlen maradt a híd kiesése alatt (${CFG.agentLabel}): ${ids.map((m) => `msg=${m}`).join(", ")}`);
  };
  const onResult = (r) => {
    logNotice(CFG.inboxDir, `inbound_${r.status}`,
      { chat_id: r.chat_id, msg_id: r.msg_id, ...(r.detail ? { detail: r.detail } : {}) });
    if (r.status !== "unconfirmed") return;
    // Hianyzo transzkript = beallitasi hiba, nem uzenet-vesztes: folyamatonkent EGY
    // riasztas, reakcio nelkul (kulonben minden bejovo uzenet riasztana).
    if (r.detail === "no transcript") {
      if (noTranscriptAlerted) return;
      noTranscriptAlerted = true;
      say(`${CFG.agentLabel} transzkriptje nem található — a beérkezés nem igazolható (session.id / BRIDGE_TRANSCRIPT_ROOT?)`);
      return;
    }
    // Rég lejárt (a híd kiesése alatt): egy körön belül EGY összesítő riasztás, reakció nélkül.
    if (r.detail === "stale") { staleIds.push(r.msg_id); return; }
    if (r.chat_id === "todo") { // todo-ebresztes: nincs Telegram-uzenet, amire reagalni lehetne
      say(`todo-ébresztés wake=${r.msg_id} nem jelent meg ${CFG.agentLabel} transzkriptjében (újrainjektálás után sem)`);
      return;
    }
    say(`msg=${r.msg_id} nem jelent meg ${CFG.agentLabel} transzkriptjében (újrainjektálás után sem)`);
    react(r.chat_id, Number(r.msg_id));
  };
  const receipts = createReceipts({
    file: CFG.receiptFile, sessionIdFile: CFG.sessionIdFile, transcriptRoot: CFG.transcriptRoot,
    reinject: (l) => delivery?.deliver(l), onResult, onCheckEnd, log, onCorrupt,
    ...(now ? { now } : {}), ...(windowMs ? { windowMs } : {}),
  });
  let timer = null;
  return {
    hooks: { beforeInject: (l) => receipts.measure(l), onInjected: (l) => receipts.record(l) },
    bind: (d) => { delivery = d; },
    start: () => {
      if (timer) return;
      timer = setInterval(() => {
        try { receipts.check(); } catch (e) { log("nyugta-ellenőrzés hiba:", e.message); }
      }, checkMs);
      timer.unref?.();
    },
    stop: () => { clearInterval(timer); timer = null; },
    check: () => receipts.check(),
    depth: () => receipts.depth(),
  };
}
