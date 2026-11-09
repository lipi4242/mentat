// lib/send-args.mjs — a send.mjs parancssora. Szigoru: ismeretlen `--x`
// kapcsolo exit 64, SEMMI nem megy ki. A `--` utan minden szo szerint szoveg.
// A csendes felresiklas (lenyelt opcio-ertek, `--reply-to nope` -> NaN, egy
// elgepelt kapcsolo a szovegben) rosszabb a hangos hibanal.

export class UsageError extends Error {
  constructor(msg, code = 1) { super(msg); this.code = code; }
}

export const USAGE =
  "usage: send.mjs --chat <id> [--reply-to <id>] [--] <text>\n" +
  "       send.mjs --chat <id> --text-stdin [--reply-to <id>]\n" +
  "       send.mjs --chat <id> --react <emoji> --message <msg_id>\n" +
  "       send.mjs --chat <id> --photo <path.png|jpg|jpeg|webp> [--caption <text> | --caption-stdin] [--reply-to <id>]\n" +
  "         (caption max 1024 karakter, plain text; fajl max 10 MB; nem kombinalhato szoveggel/--react-tel)\n" +
  "  hosszu uzenetnel: --why \"<egy mondat, miert kell ennyi>\"\n" +
  "  formazott uzenet: --html (csak a Telegram engedte tagek: b i u s code pre a blockquote tg-spoiler)\n" +
  "  --dry-run: minden elofeltetel (token, chat, kapcsolok, kapu, naplo) Telegram-hivas nelkul; semmi nem megy ki\n" +
  "  --instance <id>: ELAVULT, figyelmen kivul hagyva\n" +
  "  a -- utan minden szo szerint szoveg (kapcsolonak latszo szo is)\n" +
  "  4096 feletti plain text automatikusan (i/n) darabokra bomlik; --html 4096 felett exit 4\n" +
  "exit codes: 0 confirmed, 1 usage error or failed (a Telegram elutasitotta, NEM ment ki), " +
  "3 confirmed BUT the delivery log was not written (BRIDGE_STATE_DIR?), " +
  "4 hosszusag-kapu: a hatar folott indoklas nelkul, vagy --html 4096 felett (SEMMI nem ment ki), " +
  "5 unknown: a keres elment, valasz nem jott (timeout) — lehet, hogy kiment, " +
  "64 ismeretlen kapcsolo (SEMMI nem ment ki)";

const KNOWN_VALUE = new Set(["--chat", "--reply-to", "--react", "--message", "--why", "--instance", "--photo", "--caption"]);
const KNOWN_FLAG = new Set(["--text-stdin", "--html", "--caption-stdin", "--dry-run"]);

const positiveInt = (flag, v) => {
  const n = /^\d+$/.test(String(v).trim()) ? Number(v) : NaN;
  // 0 nem uzenet-id; 2^53 felett a Number csendben kerekit (mas uzenetre mutatna)
  if (!(Number.isSafeInteger(n) && n > 0)) throw new UsageError(`${flag} must be a positive integer, got: ${v}`);
  return n;
};

// `deprecated` csak akkor kerul a kimenetbe, ha nem ures (a regi alak valtozatlan).
export function parseArgs(argv) {
  const out = { chat: null, replyTo: null, react: null, messageId: null,
    textStdin: false, why: null, html: false, text: "" };
  const deprecated = [];
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--") { rest.push(...argv.slice(i + 1)); break; } // utana: SZOVEG, szo szerint
    if (KNOWN_FLAG.has(a)) {
      if (a === "--caption-stdin") out.captionStdin = true; // photo-mezok CSAK hasznalatkor (a regi alak valtozatlan)
      else if (a === "--dry-run") out.dryRun = true; // ez is csak hasznalatkor kerul a kimenetbe
      else out[a === "--html" ? "html" : "textStdin"] = true;
      continue;
    }
    if (KNOWN_VALUE.has(a)) {
      if (i + 1 >= argv.length) throw new UsageError(`${a} requires a value`);
      const v = argv[++i];
      // egy kapcsolo nem lehet ertek: `--chat --html` elgepeles, nem chat-id
      if (v.startsWith("--")) throw new UsageError(`${a} requires a value, got option: ${v}`);
      if (a === "--chat") out.chat = v;
      else if (a === "--reply-to") out.replyTo = positiveInt(a, v);
      else if (a === "--react") out.react = v;
      else if (a === "--message") out.messageId = positiveInt(a, v);
      else if (a === "--why") out.why = v;
      else if (a === "--photo") out.photo = v;
      else if (a === "--caption") out.caption = v;
      else deprecated.push("--instance"); // 2.0.x kompat: az ertek eldobva
      continue;
    }
    if (a.startsWith("--")) throw new UsageError(`ismeretlen kapcsolo: ${a} (szovegkent: tedd a -- utan)`, 64);
    rest.push(a);
  }
  out.text = rest.join(" ");
  if (out.textStdin && out.text) throw new UsageError("--text-stdin cannot be combined with positional text");
  if (out.photo !== undefined) {
    if (out.text || out.textStdin || out.react || out.html)
      throw new UsageError("--photo cannot be combined with text, --text-stdin, --html or --react");
    if (out.caption !== undefined && out.captionStdin)
      throw new UsageError("--caption and --caption-stdin are mutually exclusive");
  } else if (out.caption !== undefined || out.captionStdin) {
    throw new UsageError("--caption/--caption-stdin require --photo");
  }
  if (deprecated.length) out.deprecated = deprecated;
  return out;
}
