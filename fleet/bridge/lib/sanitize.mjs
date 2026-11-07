// lib/sanitize.mjs — a bejövő Telegram-szöveg/név tisztító tiszta függvényei.
//
// Miért közös modul: a bridge.mjs inbound injektálása ÉS az 1.2-es listener-út
// egyaránt erre a két függvényre támaszkodik, hogy a stream-tartalom (Telegram
// üzenetszöveg, profilnév, reakció-emoji) ne tudjon hamis protokoll-sort vagy
// kontroll-karaktert csempészni a tmux sessionbe — lásd bridge.mjs fejléc-
// kommentjét a Codex-bírálatról (2026-07-30).

// A Telegram szövegüzenet saját plafonja. Eddig 1500 volt itt, és a vágás NÉMA:
// 2026-09-17-én egy 2473 karakteres feladatleírás a 3. pont közepén ért
// véget egy ágensnél, jelzés nélkül (events log: teljes). Egy hosszú üzenet
// félig célba érni rosszabb, mint egyáltalán nem — ezért a plafon a Telegramé,
// és ha mégis vágunk, a sor végén ott a jel és a hiányzó karakterszám.
export const MAX_TEXT = 4096;

// Tisztitas: egyetlen sor, terminal-biztosan: kontroll-karakterek (ANSI ESC, CR,
// BEL, backspace mind a \x00-\x1f\x7f savban), PLUSZ bidi-kontrollok es zero-width
// karakterek (a Codex-birálat pontja: iranymanipulacio/lathatatlan szoveg ne
// erjen promptot).
const clean = (t) => String(t)
  .replace(/[\x00-\x1f\x7f]+/g, " ")
  .replace(/[​-‏‪-‮⁦-⁩﻿]/g, "")
  .replace(/\s+/g, " ").trim();

export function sanitize(text, max = MAX_TEXT) {
  const c = clean(text);
  if (c.length <= max) return c;
  const missing = c.length - max;
  return `${c.slice(0, max)} […csonkítva: +${missing} karakter, a teljes szöveg az events logban]`;
}

// Bejovo uzenettorzs: a teljes szoveg az events-naploban MINDIG megvan; ha vagunk,
// a sor vegen kimondjuk, hol (918b13b, 2026-10-08: 2001 karakter nemán vagodott).
export const MAX_BODY_CHARS = 6000;
// A jel a keretbe beleszamit (kimenet <= max); surrogate par nem torik kette.
export function sanitizeBody(text, { max = MAX_BODY_CHARS, where = "az events-naploban" } = {}) {
  const c = clean(text);
  if (c.length <= max) return c;
  const marker = ` [CSONKA: teljes szöveg ${where}]`;
  let k = Math.max(0, max - marker.length);
  const h = c.charCodeAt(k - 1);
  if (h >= 0xd800 && h <= 0xdbff) k -= 1;
  return `${c.slice(0, k)}${marker}`;
}

// Fájlnév-komponens: SOHA nem a küldő adatából — csak chat/message azonosítóból.
export function safeName(part) {
  return String(part).replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 64);
}
