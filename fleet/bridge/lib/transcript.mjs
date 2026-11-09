// lib/transcript.mjs — a Claude-transzkript (JSONL) olvasasa az erkezes-nyugtahoz (3.2).
// Csak olvas; minden hiba "nincs" / "nem talalt" — sosem dob.
import { readdirSync, statSync, openSync, readSync, closeSync, readFileSync } from "node:fs";
import { join } from "node:path";

export function readSessionId(file) {
  try { return readFileSync(file, "utf8").trim() || null; } catch { return null; }
}

// <root>/*/<sid>.jsonl — az elso talalat (rendezett konyvtarsorrendben).
export function findTranscript(root, sid) {
  if (!sid || /[\/\\]/.test(sid)) return null;
  let dirs = [];
  try { dirs = readdirSync(root); } catch { return null; }
  for (const d of dirs.sort()) {
    const p = join(root, d, `${sid}.jsonl`);
    try { if (statSync(p).isFile()) return p; } catch { /* nincs itt */ }
  }
  return null;
}

export const sizeOf = (p) => { try { return statSync(p).size; } catch { return 0; } };
// Fajl-azonossag: az azonos vagy nagyobb meretu CSERE (uj inode) is offset-nullazast ker.
export const identOf = (p) => { try { const s = statSync(p); return `${s.dev}:${s.ino}`; } catch { return null; } };

// A fejlec pontos alakja (lib/lines.mjs), a user-szoveg ELEJEHEZ kotve; lusta `.*?`,
// mert a megjelenitett nevben lehet `]` (pl. "Alice [work]"). Az `id=\d+ | chat=`
// horgony miatt a nevben allo `| chat=… | msg=…` nem ad hamis kulcsot. `msg=12` != `msg=123`.
// SORKEZDETHEZ kotve ("m"): a valodi Claude Code (2.1.302) egy elnyelt Enter utan
// ket injektalt sort EGY user-bejegyzesbe fuz "\n"-nel; a torzs sosem tartalmaz
// ujsort (sanitizeBody), tehat sorkezdo fejlec csak kulon injektalt sorbol johet.
export const HEADER_HEAD = String.raw`^\[Telegram inbound \| .*? id=\d+ \| chat=`;
// Todo-ebresztes (lib/todo-lines.mjs): `[Todo | ... | wake=<seq>]:` — a chat helyen "todo".
// A wake= a fejlec UTOLSO mezoje; a cim a `]: ` utan all, tehat a fejlecbe nem csuszhat.
export const TODO_HEAD = String.raw`^\[Todo \| [^\]\n]*?\| wake=`;
export const headerRe = (chat, msg) => (chat === "todo"
  ? new RegExp(String.raw`${TODO_HEAD}${msg}\]: `, "m")
  : new RegExp(String.raw`${HEADER_HEAD}${chat} \| msg=${msg}(?=[ |\]])`, "m"));

// string, vagy [{type:"text",text}] tomb
const textOf = (c) => {
  if (typeof c === "string") return c;
  if (Array.isArray(c)) return c.filter((x) => x?.type === "text" && typeof x.text === "string")
    .map((x) => x.text).join("\n");
  return null;
};

// A user-bejegyzes szovege. Amig az agens dolgozik, a tmux-ba gepelt prompt
// `{type:"attachment", attachment:{type:"queued_command", prompt}}` alakban all.
export function userText(o) {
  if (o?.type === "user") return textOf(o.message?.content);
  if (o?.type === "attachment" && o.attachment?.type === "queued_command") return textOf(o.attachment.prompt);
  return null;
}

// Teszt-varrat: osszes olvasott bajt (ujraolvasas-mentesseg) es a legnagyobb puffer.
export const readStats = { bytes: 0, maxBuf: 0 };
export const WINDOW = 1024 * 1024; // rogzitett olvasasi ablak (MemoryMax=96M unit)
export const TAIL = 8 * 1024 * 1024; // uj utvonalnal ennyit nezunk vissza a vegetol
const PROBE = 64 * 1024; // a sorhatar-kereses lepese

function readAt(fd, len, pos) {
  const buf = Buffer.alloc(len);
  readStats.maxBuf = Math.max(readStats.maxBuf, len);
  const n = readSync(fd, buf, 0, len, pos);
  readStats.bytes += n;
  return n < len ? buf.subarray(0, n) : buf;
}

// Uj utvonal kezdo offsetje: max(0, size - TAIL), a kovetkezo sorhatarig elore lepve.
export function tailOffset(path, tail = TAIL) {
  const size = sizeOf(path);
  if (size <= tail) return 0;
  let fd;
  try { fd = openSync(path, "r"); } catch { return 0; }
  try {
    for (let pos = size - tail - 1; pos < size;) {
      const buf = readAt(fd, Math.min(PROBE, size - pos), pos);
      if (!buf.length) break;
      const nl = buf.indexOf(0x0a);
      if (nl >= 0) return pos + nl + 1;
      pos += buf.length;
    }
    return size;
  } catch { return 0; } finally { closeSync(fd); }
}

// Az offset UTANI, TELJES (\n-nel lezart) sorok user-bejegyzesei:
// `{ entries: [{pos, text}], end }` — `end` = az utolso teljes sor vege (bajt).
// WINDOW-nyi ablakokban olvas; a sor-maradek atvive. A WINDOW-nal hosszabb sor
// (pl. base64 kep) atugorva — Telegram-sor sosem ekkora.
export function scanUserEntries(path, offset) {
  const out = { entries: [], end: offset };
  const size = sizeOf(path);
  if (size <= offset) return out;
  let fd;
  try { fd = openSync(path, "r"); } catch { return out; }
  const take = (buf, at) => {
    const line = buf.toString("utf8");
    if (!line.includes("Telegram inbound") && !line.includes("[Todo |")) return;
    let o;
    try { o = JSON.parse(line); } catch { return; }
    const t = userText(o);
    if (t) out.entries.push({ pos: at, text: t });
  };
  try {
    let carry = Buffer.alloc(0), carryAt = offset, skipping = false;
    for (let pos = offset; pos < size;) {
      const buf = readAt(fd, Math.min(WINDOW, size - pos), pos);
      if (!buf.length) break;
      let start = 0;
      for (let nl = buf.indexOf(0x0a); nl >= 0; start = nl + 1, nl = buf.indexOf(0x0a, start)) {
        if (!skipping && carry.length + nl - start <= WINDOW) take(carry.length ? Buffer.concat([carry, buf.subarray(start, nl)]) : buf.subarray(start, nl), carryAt);
        carry = Buffer.alloc(0); skipping = false;
        carryAt = pos + nl + 1;
        out.end = carryAt;
      }
      if (!skipping) {
        const rest = buf.subarray(start);
        if (carry.length + rest.length > WINDOW) { skipping = true; carry = Buffer.alloc(0); }
        else carry = Buffer.concat([carry, rest]);
      }
      pos += buf.length;
    }
  } catch { /* reszleges eredmeny */ } finally { closeSync(fd); }
  return out;
}
