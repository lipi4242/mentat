#!/usr/bin/env node
// send.mjs — sub-etha kimeno irany. Plain text (nincs parse_mode -> nincs
// formazas-injekcio), a szoveg sosem er shellt, token env-bol. Hasznalat:
//   TELEGRAM_BOT_TOKEN=... node send.mjs --chat <id> [--reply-to <msg_id>] -- "szoveg"
// Sikeres kuldesnel a message_id megy stdout-ra (darabolt uzenetnel soronkent).
// 4096 UTF-16 kodegyseg folott a plain text (i/n) darabokban megy (lib/chunk.mjs).
//
// Minden kuldes es reakcio a kezbesitesi naploba kerul (lib/outbound.mjs,
// docs/delivery-log.md): szandek ELORE, kimenet utana. A Telegram nem adja
// vissza a bot sajat uzeneteit — "kiment-e a valasz" csak innen tudhato.
import { appendFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolveLogDir } from "./lib/delivery-log.mjs";
import { sendWithLog } from "./lib/outbound.mjs";
import { sendParts } from "./lib/send-run.mjs";
import { splitForTelegram } from "./lib/chunk.mjs";
import { gateLimit, checkLength, justificationRow } from "./lib/length-gate.mjs";
import { sanitizeHtml } from "./lib/html.mjs";
import { parseArgs, USAGE } from "./lib/send-args.mjs";
import { checkCaption, checkPhotoFile, sendPhotoCall } from "./lib/photo.mjs";
import { basename } from "node:path";
import { logNotice } from "./lib/notice.mjs";

const MAX_LEN = 4096;

export function buildPayload(chatId, text, replyTo, opts = {}) {
  const p = { chat_id: chatId, text: (text || "").slice(0, MAX_LEN), disable_web_page_preview: true };
  if (replyTo) p.reply_to_message_id = replyTo;
  // --html: a szoveg a lib/html.mjs szurojen megy at, es CSAK ekkor kap parse_mode-ot.
  if (opts.html) p.parse_mode = "HTML";
  return p;
}

export function buildReactionPayload(chatId, messageId, emoji) {
  return { chat_id: chatId, message_id: messageId, reaction: [{ type: "emoji", emoji }] };
}

export { parseArgs, USAGE } from "./lib/send-args.mjs";

// A teljes stdin UTF-8-kent, vagas nelkul (fix argv, a szoveg csovon jon).
export function readStdinText() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { data += chunk; });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

// Az indokok gyujtese. SOSEM buktatja meg a kuldest.
export function logJustification(gate, args, env = process.env) {
  const dir = env.BRIDGE_STATE_DIR;
  if (!dir) return;
  try {
    const row = justificationRow({ chatId: args.chat, len: gate.len, limit: gateLimit(env),
      why: gate.why, agent: env.SUBETHA_AGENT || null });
    appendFileSync(`${dir}/length-gate.jsonl`, `${JSON.stringify(row)}\n`);
  } catch (e) {
    console.error(`indok-napló irasa sikertelen (a kuldes megy tovabb): ${e.message}`);
  }
}

// SUBETHA_TELEGRAM_API: csak tesztnek (helyi hamis Telegram); SUBETHA_SEND_TIMEOUT_MS: alap 20 s.
function telegramCaller(token, env) {
  const base = env.SUBETHA_TELEGRAM_API || "https://api.telegram.org";
  const timeoutMs = Number(env.SUBETHA_SEND_TIMEOUT_MS || 20_000);
  return (method, payload) => async () => {
    const res = await fetch(`${base}/bot${token}/${method}`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(timeoutMs),
    });
    return res.json();
  };
}

export async function main(argv = process.argv.slice(2), env = process.env) {
  const token = env.TELEGRAM_BOT_TOKEN;
  if (!token) { console.error("missing TELEGRAM_BOT_TOKEN"); return 1; }
  const logDir = resolveLogDir(env, fileURLToPath(import.meta.url));
  let args;
  try { args = parseArgs(argv); } catch (e) { console.error(`${e.message}\n${USAGE}`); return e.code ?? 1; }
  if (args.deprecated?.length) {
    console.error("FIGYELEM: --instance elavult (2.0.x), figyelmen kivul hagyva — a kovetkezo kiadas kiveszi");
    logNotice(logDir, "deprecated_flag", { detail: "--instance", chat_id: args.chat });
  }
  if (args.textStdin) args.text = await readStdinText();
  const call = telegramCaller(token, env);

  if (args.photo !== undefined) {
    if (!args.chat) { console.error(USAGE); return 1; }
    if (args.captionStdin) args.caption = await readStdinText();
    const caption = args.caption || "";
    // Minden kapu a szandek-sor ELOTT: ami itt megall, el sem indult (exit 1, SEMMI nem megy ki).
    try { checkPhotoFile(args.photo); } catch (e) { console.error(`${e.message}\n${USAGE}`); return 1; }
    const cap = checkCaption(caption);
    if (!cap.ok) { console.error(`${cap.message}\n${USAGE}`); return 1; }
    // Hosszusag-kapu a captionre is (mint a szovegnel): a Telegram 1024-es hatara csak a MASODIK kapu.
    if (caption) {
      const gate = checkLength({ text: caption, why: args.why, limit: gateLimit(env) });
      if (!gate.ok) { console.error(gate.message); return 4; }
      if (gate.over) logJustification(gate, args, env);
    }
    const r = await sendWithLog({ logDir,
      intent: { chat_id: args.chat, action: "message", reply_to: args.replyTo ?? undefined,
        media: "photo", text: caption || `[kep ${basename(args.photo)}]` },
      call: sendPhotoCall({ token, env, chatId: args.chat, path: args.photo, caption, replyTo: args.replyTo }) });
    if (r.messageId != null) console.log(String(r.messageId));
    if (r.status !== "confirmed") console.error(`sendPhoto ${r.status}: ${r.error}`);
    return r.code;
  }

  if (args.react) {
    if (!args.chat || !args.messageId) { console.error(USAGE); return 1; }
    const r = await sendWithLog({ logDir,
      intent: { chat_id: args.chat, action: "reaction", target_msg_id: args.messageId, text: args.react },
      call: call("setMessageReaction", buildReactionPayload(args.chat, args.messageId, args.react)) });
    if (r.status !== "confirmed") console.error(`setMessageReaction ${r.status}: ${r.error}`);
    return r.code;
  }
  if (!args.chat || !args.text) { console.error(USAGE); return 1; }
  // Hosszusag-kapu — a kuldes (es a szandek-sor) ELOTT: ami itt megall, el sem indult.
  const gate = checkLength({ text: args.text, why: args.why, limit: gateLimit(env) });
  if (!gate.ok) { console.error(gate.message); return 4; }
  if (gate.over) logJustification(gate, args, env);
  const text = args.html ? sanitizeHtml(args.text) : args.text;
  if (args.html && text.length > MAX_LEN) {
    console.error("--html 4096 felett nem darabolhato (a tag-ek szetvagnanak) — SEMMI nem ment ki");
    return 4;
  }
  const parts = args.html ? [text] : splitForTelegram(text, MAX_LEN);
  const r = await sendParts({ logDir, chatId: args.chat, replyTo: args.replyTo, parts,
    makeCall: (t, rt) => call("sendMessage", buildPayload(args.chat, t, rt, { html: args.html })) });
  for (const id of r.ids) if (id != null) console.log(String(id));
  if (r.error) console.error(`sendMessage ${r.error}`);
  return r.code;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().then((c) => process.exit(c), (e) => { console.error(String(e)); process.exit(1); });
}
