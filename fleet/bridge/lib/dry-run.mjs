// lib/dry-run.mjs — `send.mjs --dry-run`: a kuldes minden elofeltetele, Telegram-hivas NELKUL.
//
// 11-07: harom agens nemán nem tudott irni a tulajdonosnak (nem volt token a unit env-jeben),
// es minden egeszsegjel zold volt. A `fleet doctor`/postcheck kepesseg-probaja ezt futtatja,
// a unit env-fajljaival: token (csak a LETE es az alakja, az erteke sosem kerul kimenetre),
// chat, a kapcsolok, a hosszusag-kapu es a kezbesitesi naplo irhatosaga. A naploba SEM ir:
// a proba nem kuldes, a doctor ne lassa kuldesnek.
//
// Kilepesi kodok (a send.mjs-sel egyezoen): 0 kuldheto · 1 hiba (token/chat/kapcsolo) ·
// 3 a kezbesitesi naplo nem irhato · 4 hosszusag-kapu.
import { accessSync, constants, mkdirSync } from "node:fs";
import { checkLength, gateLimit } from "./length-gate.mjs";
import { checkCaption, checkPhotoFile } from "./photo.mjs";

// A Bot API tokenje `<bot-id>:<35 karakter>`; a hamis/csonka ertek itt latszik, nem a Telegramnal.
const TOKEN_SHAPE = /^\d{5,}:[A-Za-z0-9_-]{30,}$/;
const CHAT_SHAPE = /^(-?\d+|@[A-Za-z0-9_]{5,})$/;

export function dryRun(args, env, logDir) {
  const fail = (code, msg) => ({ code, lines: [`dry-run HIBA: ${msg}`] });
  if (!env.TELEGRAM_BOT_TOKEN) return fail(1, "missing TELEGRAM_BOT_TOKEN (a unit env-jebol kell jonnie)");
  if (!TOKEN_SHAPE.test(env.TELEGRAM_BOT_TOKEN)) return fail(1, "a TELEGRAM_BOT_TOKEN alakja hibas (<bot-id>:<kulcs>)");
  if (!args.chat) return fail(1, "nincs --chat");
  if (!CHAT_SHAPE.test(String(args.chat))) return fail(1, "a --chat nem chat-azonosito (szam vagy @nev)");
  let text = args.text;
  if (args.photo !== undefined) {
    try { checkPhotoFile(args.photo); } catch (e) { return fail(1, e.message); }
    const cap = checkCaption(args.caption || "");
    if (!cap.ok) return fail(1, cap.message);
    text = args.caption || "";
  } else if (args.react) {
    if (!args.messageId) return fail(1, "--react --message nelkul");
    text = "";
  } else if (!args.textStdin && !text) {
    return fail(1, "nincs szoveg");
  }
  const gate = checkLength({ text, why: args.why, limit: gateLimit(env) });
  if (!gate.ok) return { code: 4, lines: [`dry-run HIBA: ${gate.message}`] };
  if (!logDir) return fail(3, "a kezbesitesi naplo helye ismeretlen (BRIDGE_STATE_DIR / sub-etha/)");
  try {
    mkdirSync(logDir, { recursive: true });
    accessSync(logDir, constants.W_OK);
  } catch (e) {
    return fail(3, `a kezbesitesi naplo nem irhato (${e.code || e.message})`);
  }
  const what = args.photo !== undefined ? "kep" : args.react ? "reakcio" : "szoveg";
  return { code: 0, lines: [`dry-run OK: token megvan, chat ${args.chat}, ${what}, naplo irhato — semmi nem ment ki`] };
}
