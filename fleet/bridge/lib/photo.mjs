// lib/photo.mjs — a send.mjs --photo mod segedei (kapuk + multipart sendPhoto). Telegram sendPhoto: multipart/form-data,
// caption max 1024 karakter, plain text (nincs parse_mode), fajl <= 10 MB.
import { readFileSync, statSync } from "node:fs";
import { extname, basename } from "node:path";

export const MAX_CAPTION = 1024;
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
export const PHOTO_TYPES = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

// checkCaption — a prefixalt caption hossza. A Telegram a 1024 felett
// elutasitana; mi HANGOSAN, kuldes elott utasitjuk el (nem vagunk csendben).
export function checkCaption(caption) {
  const len = (caption || "").length; // UTF-16 egyseg: igy szamol a Telegram es a send.mjs tobbi resze
  if (len > MAX_CAPTION)
    return { ok: false, len, message: `caption tul hosszu: ${len} > ${MAX_CAPTION} karakter (Telegram-hatar); semmi nem ment ki` };
  return { ok: true, len };
}

// checkPhotoFile — kiterjesztes + letezes + meret. Dob usage-hibat (Error).
export function checkPhotoFile(path, statFn = statSync) {
  const type = PHOTO_TYPES[extname(path || "").toLowerCase()];
  if (!type)
    throw new Error(`--photo: csak ${Object.keys(PHOTO_TYPES).join("/")} fogadhato el, got: ${path}`);
  let st;
  try { st = statFn(path); } catch { throw new Error(`--photo: a fajl nem letezik: ${path}`); }
  if (!st.isFile()) throw new Error(`--photo: nem fajl: ${path}`);
  if (st.size > MAX_PHOTO_BYTES)
    throw new Error(`--photo: ${st.size} bajt > ${MAX_PHOTO_BYTES} (10 MB hatar): ${path}`);
  if (st.size === 0) throw new Error(`--photo: ures fajl: ${path}`);
  return { type, size: st.size };
}

// buildPhotoForm — FormData a sendPhoto-hoz. A caption plain text: NINCS
// parse_mode mezo. A reply_to opcionalis.
export function buildPhotoForm({ chatId, path, caption, replyTo, readFn = readFileSync }) {
  const type = PHOTO_TYPES[extname(path || "").toLowerCase()];
  if (!type) throw new Error(`--photo: nem tamogatott kiterjesztes: ${path}`);
  const form = new FormData();
  form.set("chat_id", String(chatId));
  if (caption) form.set("caption", caption);
  if (replyTo) form.set("reply_to_message_id", String(replyTo));
  form.set("photo", new Blob([readFn(path)], { type }), basename(path));
  return form;
}

// sendPhotoCall — makeCall-forma (mint a send-run.mjs): async () => Telegram-valasz-body.
// Az env-bol: SUBETHA_TELEGRAM_API (teszt), SUBETHA_PHOTO_TIMEOUT_MS (alap 60 s kep-feltoltesre).
export function sendPhotoCall({ token, env = process.env, chatId, path, caption, replyTo }) {
  const base = env.SUBETHA_TELEGRAM_API || "https://api.telegram.org";
  const timeoutMs = Number(env.SUBETHA_PHOTO_TIMEOUT_MS || 60_000);
  return async () => {
    const res = await fetch(`${base}/bot${token}/sendPhoto`, {
      method: "POST",
      body: buildPhotoForm({ chatId, path, caption, replyTo }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    return res.json();
  };
}
