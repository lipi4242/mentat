// lib/albums.mjs — media (kep + hang) feldolgozasa; a media_group_id egy
// sorba fogva (kulonben 5 kep = 5 prompt).
//
// MIERT TARTOS A PUFFER: a media-sor eleme akkor "kesz", amikor a handleMedia
// VISSZATER — az a pufferelés + a debounce-idozito beallitasa utan van, nem a
// kezbesites utan. Ha a puffer csak memoriaban elne, egy ebben az ablakban
// bekovetkezo osszeomlas nemán vinne el a sorelemet. Ezert a puffer lemezen is
// el, es indulaskor MINDEN benne maradt album azonnal kimegy (resume).
// Duplikalas elkepzelheto — "inkabb ketszer, mint hogy elvesszen".
import { join } from "node:path";
import { saveJsonStrict, loadJsonQuarantine } from "./jsonfile.mjs";
import { sanitize, safeName } from "./sanitize.mjs";
import { buildMediaLine } from "./lines.mjs";

export function createAlbums({
  file, inboxDir, debounceMs, maxBytes, deliver, download,
  alert = async () => {}, log = () => {}, onCorrupt = () => {},
}) {
  const albums = new Map();
  const timers = new Map(); // key -> Timeout; SOHA nem megy lemezre
  let flushAlerted = false;

  // STRIKT: a puffer az egyetlen tartos masolat egy meg ki nem kuldott albumrol.
  const save = () => saveJsonStrict(file, Object.fromEntries(albums));

  function flush(key) {
    const t = timers.get(key);
    if (t) clearTimeout(t);
    timers.delete(key);
    const a = albums.get(key);
    if (!a) return;
    // ELOBB kezbesites (hiba eseten a tartos pending-sorba), CSAK UTANA torles.
    if (a.paths.length || a.failures.length) deliver(buildMediaLine(a));
    albums.delete(key);
    save();
  }

  // Idozitobol/resume-bol hivva nincs poll-ciklus, ami elkapna a hibat: egy
  // dobas a hid halala lenne. Hiba eseten az album a pufferben MARAD.
  function flushSafe(key) {
    try {
      flush(key);
      flushAlerted = false;
    } catch (e) {
      log("album kiküldés hiba (a puffer megmarad, restart újrapróbálja):", e.message);
      if (!flushAlerted) {
        flushAlerted = true;
        alert(`egy album kiküldése nem sikerült (${e.message}) — a puffer megmaradt, restart után újrapróbálom.`)
          .catch(() => {});
      }
    }
  }

  function resume() {
    const stored = loadJsonQuarantine(file, {}, onCorrupt);
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) return 0;
    const keys = Object.keys(stored);
    for (const k of keys) albums.set(k, stored[k]);
    for (const k of keys) flushSafe(k);
    return keys.length;
  }

  async function handleMedia(msg, media, updateId) {
    const chatId = String(msg.chat?.id);
    const caption = msg.caption ? sanitize(msg.caption, Infinity) : ""; // a vagas a sorepitonel (CSONKA-jel)
    const key = msg.media_group_id ? `mg:${msg.media_group_id}` : `m:${msg.message_id}`;
    if (!albums.has(key)) {
      albums.set(key, {
        who: msg.from?.first_name || msg.from?.username || String(msg.from?.id),
        fromId: String(msg.from?.id), chatId, messageId: msg.message_id,
        paths: [], failures: [], kinds: [], caption,
        ...(updateId != null ? { updateId } : {}),
      });
    }
    const a = albums.get(key);
    if (caption && !a.caption) a.caption = caption;
    a.kinds.push(media.kind);
    const mb = (n) => Math.round((n || 0) / 1024 / 1024);
    if (media.tooBig) {
      a.failures.push(`túl nagy (${mb(media.fileSize)} MB, limit ${mb(maxBytes)} MB) — kérd el kisebb méretben vagy linken`);
    } else {
      const day = new Date().toISOString().slice(0, 10);
      const destNoExt = join(inboxDir, day, `${safeName(chatId)}_${safeName(msg.message_id)}_${a.paths.length}`);
      const fallbackExt = media.kind === "voice" ? "oga" : media.kind === "audio" ? "mp3" : "jpg";
      try {
        const dest = await download({ fileId: media.fileId, destNoExt, fallbackExt });
        a.paths.push(dest);
        log(`downloaded ${dest}`);
      } catch (e) {
        a.failures.push(`letöltés nem sikerült: ${e.message}`);
        log("download failed:", e.message);
      }
    }
    // A puffer lemezre kerul, MIELOTT a sorelem kesznek szamitana.
    save();
    const prev = timers.get(key);
    if (prev) clearTimeout(prev);
    timers.set(key, setTimeout(() => flushSafe(key), debounceMs));
  }

  return { handleMedia, resume };
}
