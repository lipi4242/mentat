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

// Tisztitas: egyetlen sor, terminal-biztosan, lathatatlan szoveg nelkul.
// FL-11: a regi tiltolista (\x00-\x1f, 200B-200F, 202A-202E, 2066-2069,
// FEFF) csak a felsorolt rosszat ismerte — a U+E0000-E007F tag-karakterek
// (lathatatlan ASCII-masolat: ezzel lehet a pane-be olvashatatlan utasitast
// csempeszni), a U+2060/U+00AD/U+180E es a C1-kontrollok (U+0085) atmentek.
// Most kategoria alapjan szurunk, NFKC UTAN (a teljes szelessegu "［" is "[" lesz,
// es a kompatibilitasi alakok nem bujtatnak el semmit):
//   - Cc (C0 + DEL + C1) es sor/bekezdes-elvalaszto (Zl/Zp) -> szokoz;
//   - Cf (formazo: bidi, zero-width, soft hyphen, tag-ok), Co (privat), Cs (arva
//     surrogate), minden Default_Ignorable (Hangul-kitolto, valtozat-valaszto
//     FE00-FE0F es E0100-E01EF: ezekkel is kodolhato rejtett szoveg), plusz a
//     E0000-E007F sav kifejezetten -> torolve.
// EGY hely: a bejovo szoveg, felirat, nev, reakcio (lines.mjs) es a vegso
// pane-kapu (deliverer.mjs -> paneSafe) is ezt hivja; a todo-ebresztes (#55)
// sorai ugyanezen a modulon at mennek. Ne irj ide importot: a fleet plugin
// hooks/todo/ bajtra azonos masolatot visz belole.
//   - plusz a nem Default_Ignorable, megis ures kepu jelek: U+2800 (Braille-ures),
//     U+1D159 (null notehead); es a halmozott kombinalo jel (>3 egymas utan:
//     egymasra rajzolva lathatatlanul hordozhat adatot) 3-ra vagva.
const CTRL = /[\p{Cc}\p{Zl}\p{Zp}]+/gu;
const INVISIBLE = /[\p{Cf}\p{Co}\p{Cs}\p{Default_Ignorable_Code_Point}\u{E0000}-\u{E007F}\u{E0100}-\u{E01EF}\u2800\u{1D159}]/gu;
const MARK_PILE = /(\p{M}{3})\p{M}+/gu;

const strip = (t) => t.replace(CTRL, " ").replace(INVISIBLE, "").replace(MARK_PILE, "$1");

// Lathatatlan/kontroll nelkuli, de NEM egysoritott es nem vagott alak (NFKC-val).
export function stripInvisible(t) {
  return strip(String(t).normalize("NFKC"));
}

const clean = (t) => stripInvisible(t).replace(/\s+/g, " ").trim();

// A pane-be meno KESZ sor utolso szurese (minden kezbesitesi ut kozos kapuja):
// lathatatlan/kontroll ki, egy sor marad. NFKC itt NINCS: a kesz sorban a hid
// sajat utvonalai is allnak (media-fajl, BRIDGE_STATE_DIR), azokat nem irjuk at;
// a felhasznaloi mezok a sorepitoben mar NFKC-n mentek at. Vagas sincs — azt a
// sorepito mar eldontotte, a jelevel egyutt.
export function paneSafe(line) {
  return strip(String(line)).replace(/\s+/g, " ").trim();
}

// Vagas kodpont-hataron: egy surrogate par sosem torik kette.
const cutAt = (c, k) => {
  const h = c.charCodeAt(k - 1);
  return h >= 0xd800 && h <= 0xdbff ? k - 1 : k;
};

export function sanitize(text, max = MAX_TEXT) {
  const c = clean(text);
  if (c.length <= max) return c;
  const k = cutAt(c, max);
  const missing = c.length - k;
  return `${c.slice(0, k)} […csonkítva: +${missing} karakter, a teljes szöveg az events logban]`;
}

// Bejovo uzenettorzs: a teljes szoveg az events-naploban MINDIG megvan; ha vagunk,
// a sor vegen kimondjuk, hol (918b13b, 2026-10-08: 2001 karakter nemán vagodott).
export const MAX_BODY_CHARS = 6000;
// A jel a keretbe beleszamit (kimenet <= max); surrogate par nem torik kette.
export function sanitizeBody(text, { max = MAX_BODY_CHARS, where = "az events-naploban" } = {}) {
  const c = clean(text);
  if (c.length <= max) return c;
  const marker = ` [CSONKA: teljes szöveg ${where}]`;
  const k = cutAt(c, Math.max(0, max - marker.length));
  return `${c.slice(0, k)}${marker}`;
}

// Fájlnév-komponens: SOHA nem a küldő adatából — csak chat/message azonosítóból.
export function safeName(part) {
  return String(part).replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 64);
}
