// lib/chunk.mjs — a Telegram 4096-os plafonja UTF-16 kodegysegben ertendo
// (JS .length). Darabolas (i/n) elotaggal; az elotag a keretbe beleszamit.
// Hatar-preferencia: "\n\n" -> "\n" -> " " -> kemeny vagas; surrogate par
// sosem torik kette. Tiszta fuggveny.
// Tul kicsi keret (max < MIN_MAX, vagy az elotag utan < 2 hely) RangeError:
// kulonben a cutAt 0-t adhat, es a ciklus sosem all meg.
export const MIN_MAX = 16;
const prefix = (i, n) => `(${i}/${n}) `;

function cutAt(s, budget) {
  if (s.length <= budget) return s.length;
  const win = s.slice(0, budget);
  for (const sep of ["\n\n", "\n", " "]) {
    const k = win.lastIndexOf(sep);
    if (k > 0) return k + sep.length;
  }
  const c = s.charCodeAt(budget - 1);
  return c >= 0xd800 && c <= 0xdbff ? budget - 1 : budget; // surrogate par egyben
}

function splitBody(s, budget) {
  if (budget < 2) throw new RangeError(`splitForTelegram: az elotag utan ${budget} hely marad (min 2)`);
  const out = [];
  while (s.length) { const k = cutAt(s, budget); out.push(s.slice(0, k)); s = s.slice(k); }
  return out;
}

export function splitForTelegram(text, max = 4096) {
  if (!(max >= MIN_MAX)) throw new RangeError(`splitForTelegram: max ${max} < ${MIN_MAX}`);
  const s = String(text ?? "");
  if (s.length <= max) return [s];
  let n = 2, parts;
  for (;;) { // az elotag hossza n jegyszamatol fugg — addig, amig stabil
    parts = splitBody(s, max - prefix(n, n).length);
    if (String(parts.length).length <= String(n).length) break;
    n = parts.length;
  }
  return parts.map((p, i) => prefix(i + 1, parts.length) + p);
}
