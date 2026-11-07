// lib/send-run.mjs — darabok sorban; az elso nem-confirmed darabnal megall,
// automatikus ujrakuldes NINCS (duplikalt uzenet rosszabb a hianyosnal).
// Hibanal a stderr-szoveg darabonkent nevez: failed -> "kiment / nem ment";
// unknown (timeout) -> "kiment / bizonytalan / nem probalt" — a bizonytalan
// darab se nem kiment, se nem "nem ment".
import { sendWithLog, EXIT } from "./outbound.mjs";

const label = (i, n) => `${i + 1}/${n}`;
const list = (from, to, n) => {
  const out = [];
  for (let j = from; j < to; j++) out.push(label(j, n));
  return out.join(", ") || "-";
};

function report(i, n, r) {
  const head = `darab ${label(i, n)} ${r.status}: ${r.error} — kiment: ${list(0, i, n)}`;
  if (r.status === "unknown")
    return `${head}; bizonytalan: ${label(i, n)}; nem probalt: ${list(i + 1, n, n)}`;
  return `${head}; nem ment: ${list(i, n, n)}`;
}

// makeCall(text, replyTo) -> async () => Telegram-valasz-body
// Visszater: { code, ids, error? } — ids CSAK a confirmed darabok message_id-je.
export async function sendParts({ logDir, chatId, replyTo, parts, makeCall }) {
  const ids = []; let blind = false;
  const n = parts.length;
  for (let i = 0; i < n; i++) {
    const part = n > 1 ? label(i, n) : undefined;
    const rt = i === 0 ? replyTo : null;
    const r = await sendWithLog({ logDir,
      intent: { chat_id: chatId, action: "message", reply_to: rt ?? undefined, part, text: parts[i] },
      call: makeCall(parts[i], rt) });
    if (r.status !== "confirmed") {
      // egy darab: a regi hibasor-alak (a darab-kiegeszites csak n>1-nel ertelmes);
      // a `sendMessage ` elotagot a hivo (send.mjs) teszi ele — itt nincs, kulonben dupla.
      const error = n === 1 ? `${r.status}: ${r.error}` : report(i, n, r);
      return { code: r.code, ids, error };
    }
    ids.push(r.messageId);
    if (r.code === EXIT.logBlind) blind = true;
  }
  return { code: blind ? EXIT.logBlind : EXIT.ok, ids };
}
