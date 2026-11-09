// lib/clamp.mjs — sor-meret sapkak a kezbesitesi naplo soraihoz
// (lib/delivery-log.mjs).
//
// MERET-KORLAT OKA: egy szerializalt sor ~4 KB alatt kell maradjon, hogy egy
// appendFileSync hivas lokalis ext4-en gyakorlatilag atomi legyen (a kernel
// egy 4 KB alatti write()-ot nem szeletel szet ket folyamat kozott). A sorokat
// TOBB folyamat irja ugyanabba a fajlba — egy felbeszakadt sor a kovetkezo
// olvasonak korrupt JSON.
//
// Ket lepcso (Codex P2): (1) MINDEN string boriteko-mezo 256 bajtra vagva —
// azok azonositok, nem tartalom; (2) a szoveg a fennmarado helyre vagva, majd
// vegso szerializalt ellenorzes.
export const MAX_ROW_BYTES = 4096;
export const MAX_FIELD_BYTES = 256;

// UTF-8 bajt-hataron vag (nem karakter-hataron) — folytato bajtot
// (0b10xxxxxx) SOSEM hagy a vegen, igy tobb-bajtos karakter nem torhet el.
export function clampUtf8Bytes(str, maxBytes) {
  if (maxBytes <= 0) return "";
  const buf = Buffer.from(str, "utf8");
  if (buf.length <= maxBytes) return str;
  let end = maxBytes;
  while (end > 0 && (buf[end] & 0xc0) === 0x80) end--;
  return buf.slice(0, end).toString("utf8");
}

// Egy boriteko-mezo sapkaja: a string mezoket vagjuk (UTF-8 hataron), a
// nem-string ertekeket (szam, boolean, null) valtozatlanul hagyjuk.
export function capField(v, maxBytes = MAX_FIELD_BYTES) {
  return typeof v === "string" ? clampUtf8Bytes(v, maxBytes) : v;
}

// A clamp a SZERIALIZALT sorra vonatkozik: a boriteko meretet ures text
// mellett merjuk, a fennmarado helyre vagjuk a szoveget, majd (mivel a
// JSON-escapeles novelhet a bajtszamon) egy rovid iteracioval biztositjuk,
// hogy a vegso stringify tenyleg <= maxBytes maradjon.
export function clampEntryText(entryWithoutText, text, maxBytes = MAX_ROW_BYTES) {
  if (typeof text !== "string") return text;
  const envelopeBytes = Buffer.byteLength(
    JSON.stringify({ ...entryWithoutText, text: "" }),
  );
  const budget = Math.max(0, maxBytes - envelopeBytes);
  let candidate = clampUtf8Bytes(text, budget);
  for (let i = 0; i < 8 && candidate.length > 0; i++) {
    const size = Buffer.byteLength(
      JSON.stringify({ ...entryWithoutText, text: candidate }),
    );
    if (size <= maxBytes) break;
    const overage = size - maxBytes;
    const shrinkBytes = Math.max(1, Buffer.byteLength(candidate, "utf8") - overage);
    candidate = clampUtf8Bytes(candidate, shrinkBytes);
  }
  return candidate;
}

// Vegso ellenorzes: a mezo-sapkak utan is elofordulhat (sok mezo, sok
// JSON-escapelendo karakter), hogy a szerializalt sor tullogja a hatart.
// Ilyenkor eloszor a szoveget nullazzuk; ha MEG mindig tul nagy, az mar nem
// adat, hanem hibas bemenet — HANGOSAN dobunk, nem irunk ki csonka sort.
// MELLEKHATAS: szukseg eseten uritit az entry.text-et. Az entry-t adja vissza.
export function enforceRowLimit(entry, maxBytes = MAX_ROW_BYTES, label = "") {
  if (Buffer.byteLength(JSON.stringify(entry)) <= maxBytes) return entry;
  entry.text = "";
  const size = Buffer.byteLength(JSON.stringify(entry));
  if (size > maxBytes) {
    throw new Error(
      `entry envelope ${size} bytes > ${maxBytes} even with empty text: ` +
        `malformed input${label ? ` (${label})` : ""}`,
    );
  }
  return entry;
}
