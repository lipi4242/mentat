// lib/outbound.mjs — egy Telegram-hivas a kezbesitesi naploval keretezve.
//
// Sorrend (docs/delivery-log.md): 1) intent-sor, MIELOTT a keres elindul;
// 2) a hivas; 3) outcome-sor. Ha a folyamat 2) kozben hal meg, az intent
// kimenet nelkul marad — az olvaso ezt unknown-nak latja, nem hianynak.
import { makeRow, appendDelivery } from "./delivery-log.mjs";

// A kapcsolat fel sem epult: a keres biztosan nem ert a Telegramhoz.
const NEVER_SENT = new Set(["ENOTFOUND", "EAI_AGAIN", "ECONNREFUSED", "EHOSTUNREACH", "ENETUNREACH"]);

export const EXIT = { ok: 0, failed: 1, logBlind: 3, unknown: 5 };

// Egy dobott hivas-hiba osztalyozasa: failed, ha bizonyosan el sem ment;
// minden mas (timeout, kapcsolat-bontas valasz kozben, nem-JSON valasz) unknown.
export function classifyError(e) {
  const code = e?.cause?.code || e?.code;
  return NEVER_SENT.has(code) ? "failed" : "unknown";
}

// intent: { chat_id, action: "message"|"reaction", reply_to?, target_msg_id?, text }
// call:   async () => Telegram-valasz-body
// Visszater: { code, status, messageId?, error? }
export async function sendWithLog({ logDir, intent, call, warn = (m) => console.error(m) }) {
  let blind = !logDir;
  let row = null;
  if (logDir) {
    row = makeRow({ type: "intent", ...intent });
    const res = appendDelivery(logDir, row);
    if (!res.ok) { blind = true; warn(`kezbesitesi naplo: a szandek-sor nem irodott (${res.error})`); }
  } else {
    warn("kezbesitesi naplo helye ismeretlen (BRIDGE_STATE_DIR?) — a kuldes megy, de nyoma nem marad");
  }

  let status, messageId, error;
  try {
    const body = await call();
    if (body?.ok) {
      status = "confirmed";
      messageId = body.result?.message_id;
    } else {
      status = "failed";
      error = body?.description || JSON.stringify(body).slice(0, 200);
    }
  } catch (e) {
    status = classifyError(e);
    error = e?.message || String(e);
  }

  if (row && !blind) {
    const res = appendDelivery(logDir, makeRow({
      type: "outcome", chat_id: intent.chat_id, send_id: row.id, status,
      message_id: messageId, error,
    }));
    if (!res.ok) { blind = true; warn(`kezbesitesi naplo: a kimenet-sor nem irodott (${res.error})`); }
  }

  const code = status === "failed" ? EXIT.failed
    : status === "unknown" ? EXIT.unknown
      : blind ? EXIT.logBlind : EXIT.ok;
  return { code, status, messageId, error };
}

// A hid sajat valasza a szalba (webhook-cel _REPLY): egy sendMessage, a fenti
// intent/outcome keretben. Ujrakuldes nincs (duplikatum rosszabb a hianynal).
export function createReplySender({ tg, logDir, log = () => {} }) {
  return ({ chatId, replyTo, text }) => sendWithLog({ logDir, warn: (m) => log(m),
    intent: { chat_id: chatId, action: "message", reply_to: replyTo, text },
    call: async () => (await tg("sendMessage", { chat_id: chatId, text, reply_to_message_id: replyTo })).body });
}
