// lib/length-gate.mjs — hosszusag-kapu a KIMENO uzenetekre.
//
// Miert a kuldoben es nem promptszabalyban: a hid tmux-injekcioval adja at az
// uzenetet egy elo session promptjaba, es ami egyszer bekerult a kontextusba,
// az minden tovabbi korben ujra elmegy a modellnek. Egy promptba irt
// "legyel tomor" szabaly tehat MINDEN uzenetnel fizetteti magat, orokre —
// tobbe kerulhet, mint amennyit megsporol. Ez a fuggveny viszont egy sima
// szkriptben fut: nulla tokenkoltseg, es a tomorites nem tudja kimosni.
//
// Amit a kapu NEM csinal: nem vag es nem ir at. Ha valakinek tenyleg hosszan
// kell irnia (spec, review), atmehet — de meg kell INDOKOLNIA (--why), es az
// indok naplozodik, hogy kesobb elemezheto legyen, mennyi a valodi kivetel.

export const DEFAULT_MAX_CHARS = 900;
// Az indok legyen mondat, ne pipa. A "kell" vagy "hosszu" nem elemezheto
// kesobb, es pont az elemezhetoseg miatt gyujtjuk.
export const MIN_WHY_CHARS = 15;

// gateLimit — a kapu bekapcsolt-e, es hol a hatar. Kapcsolora jar, hogy egy
// agensen be lehessen vezetni a tobbi erintese nelkul (ugyanaz a minta, mint
// a BRIDGE_REPLY_HINT-nel).
export function gateLimit(env = process.env) {
  if (!env.SUBETHA_LENGTH_GATE) return null;
  const raw = env.SUBETHA_MAX_CHARS;
  if (raw === undefined || raw === "") return DEFAULT_MAX_CHARS;
  const n = Number(raw);
  // Ertelmetlen ertek eseten a DEFAULT nyer, nem a "kapu kikapcsol": egy
  // elgepelt env sosem nyithatja ki csendben a kaput.
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : DEFAULT_MAX_CHARS;
}

// checkLength — tiszta dontes. { ok: true } vagy { ok: false, message }.
// A message MAGA az utmutato: az agens ebbol tudja, mi a harom kiutja, es
// nem kell hozza kulon szabaly a promptjaban.
export function checkLength({ text, why = null, limit = null }) {
  if (!limit) return { ok: true, over: false };
  const len = [...String(text ?? "")].length;   // karakter, nem bajt
  if (len <= limit) return { ok: true, over: false, len };
  const w = String(why ?? "").trim();
  if (!w) {
    return {
      ok: false, over: true, len,
      message: `az uzenet ${len} karakter, a hatar ${limit}. Harom kiut: ` +
        "(1) rovidebbre fogod; (2) a hosszu anyagot kiteszed valahova es CSAK " +
        "a linkjet kuldod el; (3) ha tenyleg indokolt, ujrakuldod " +
        "--why \"<egy mondat, miert kell ennyi>\" kapcsoloval.",
    };
  }
  if (w.length < MIN_WHY_CHARS) {
    return {
      ok: false, over: true, len,
      message: `a --why tul rovid (${w.length} karakter, minimum ` +
        `${MIN_WHY_CHARS}). Egy elemezheto mondat kell, nem pipa.`,
    };
  }
  return { ok: true, over: true, len, why: w };
}

// justificationRow — a naplosor alakja. Kulon fuggveny, hogy a mezoi
// tesztelhetok legyenek ora es lemez nelkul. A SZOVEG NEM kerul bele, csak a
// hossza: a napló elemzesre valo, nem uzenet-archivumnak, es egy indok-napló
// sosem lehet kiszivargasi felulet.
export function justificationRow({ chatId, len, limit, why, agent = null,
  now = Date.now() }) {
  return {
    ts: now,
    agent: agent || null,
    chat_id: String(chatId ?? ""),
    len,
    limit,
    over_by: len - limit,
    why: String(why).slice(0, 500),
  };
}
