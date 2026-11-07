// lib/media.mjs — mit tolt le a hid, es hogyan. Kep (photo / image-mime
// document) es hang (voice / audio): sok agensnel a hangjegyzet munkaeszkoz.
// A kiterjesztes a getFile file_path-jabol jon, nem fix .oga.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export function extFromPath(filePath, fallback = "bin") {
  const m = /\.([A-Za-z0-9]{1,5})$/.exec(String(filePath || ""));
  return m ? m[1].toLowerCase() : fallback;
}

// Visszater: null | {fileId, fileSize, kind} | {tooBig:true, kind, fileSize}
export function pickMedia(msg, maxBytes) {
  if (!msg) return null;
  const pick = (kind, f) => ((f.file_size || 0) > maxBytes
    ? { tooBig: true, kind, fileSize: f.file_size }
    : { fileId: f.file_id, fileSize: f.file_size || 0, kind });
  if (Array.isArray(msg.photo) && msg.photo.length) {
    const best = msg.photo.reduce((a, b) =>
      (b.file_size || b.width || 0) > (a.file_size || a.width || 0) ? b : a);
    return pick("photo", best);
  }
  const doc = msg.document;
  if (doc && String(doc.mime_type || "").startsWith("image/")) return pick("document", doc);
  for (const k of ["voice", "audio"]) if (msg[k]?.file_id) return pick(k, msg[k]);
  return null;
}

export function attachmentKind(msg) {
  for (const k of ["video", "video_note", "animation", "sticker", "document", "location", "contact", "poll"]) {
    if (msg?.[k]) return k;
  }
  return null;
}

// Letoltes a getFile-on at; a valaszbol kiolvasott ES a letoltott meret is ellenorizve.
export async function downloadMedia({ tg, fileApi, fileId, destNoExt, fallbackExt, maxBytes }) {
  const { body } = await tg("getFile", { file_id: fileId });
  if (!body.ok || !body.result?.file_path) throw new Error(`getFile: ${JSON.stringify(body).slice(0, 200)}`);
  const mb = (n) => Math.round(n / 1024 / 1024);
  const size = body.result.file_size || 0;
  if (size > maxBytes) throw new Error(`a fájl ${mb(size)} MB — a limit ${mb(maxBytes)} MB`);
  const res = await fetch(`${fileApi}/${body.result.file_path}`, { signal: AbortSignal.timeout(60_000) });
  if (!res.ok) throw new Error(`letöltés HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (!buf.length) throw new Error("üres (0 bájt) letöltés — csonka fájl");
  if (buf.length > maxBytes) throw new Error(`a letöltött tartalom ${buf.length} bájt — limit fölött`);
  const dest = `${destNoExt}.${extFromPath(body.result.file_path, fallbackExt)}`;
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, buf);
  return dest;
}
