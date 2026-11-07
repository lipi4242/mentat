// Rogzito a webhook-paritas fixturajahoz (nem teszt). A Partner-fork hidjat
// VALTOZATLANUL futtatja (a fork kodja nincs itt: a konyvtarat parameterkent
// kapja), egy gyerek-processzben, ahol a globalis fetch egy forgatokonyv-csonk:
// getMe/getUpdates/sendMessage a Telegram helyett, es a szerver-vegpontok.
//
//   node bridge/test/fixtures/webhook-paritas-recorder.mjs <fork-hid-konyvtar> <kimenet.json>
//
// A forkot a sajat main()-je hajtja: a getUpdates egyszerre EGY update-et ad,
// es csak akkor a kovetkezot, ha az elozo kiváltotta hivasok elcsendesedtek.
// Rogzitve: a szerver-kerések (vegpont, fejlec-nevek, a nyers torzs) es a
// szalba irt valaszok. Kitalalt id-k; a token nem kerul a kimenetbe.
import { spawnSync } from "node:child_process";
import { tempDir } from "../tmp.mjs";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const GROUP = -1001, BOT = 999, J = 111, K = 222, TOKEN = "TOKEN-NEM-KERUL-A-FIXTURABA";
const FOOT = "Ügy: https://admin.example.test/ugyek/ugy-42";
const botMsg = (text, id = 40) => ({ message_id: id, date: 1759990000, chat: { id: GROUP, type: "group" },
  from: { id: BOT, is_bot: true, first_name: "Bot" }, text });
const m = (o) => ({ message_id: 50, date: 1760000000, chat: { id: GROUP, type: "group" },
  from: { id: J, first_name: "Teszt" }, text: "mehet", ...o });
const r = (id, uid, date, oldR, newR) => ({ message_reaction: { chat: { id: GROUP, type: "group" },
  user: { id: uid, first_name: "Teszt" }, message_id: id, date, old_reaction: oldR, new_reaction: newR } });
const em = (e) => ({ type: "emoji", emoji: e });
const NA = { status: 404, json: { ok: false, reason: "no_anchor" } };
const OK = { status: 201, json: { ok: true, id: 7 } };
const C = (name, update, responses = {}) => ({ name, update, responses });
export const CASES = [
  C("draft-horgonyra reply, jovahagyva (lablec is van -> ugy-ag kimarad)",
    { message: m({ reply_to_message: botMsg(`Jóváhagyásra vár a levél.\n\n${FOOT}`) }) },
    { "draft-approve": { status: 200, json: { ok: true, sent: true, message: "Jóváhagyva és elküldve." } } }),
  C("reakcio a horgonyra, jovahagyva", r(40, J, 1760000100, [], [em("👍")]),
    { "draft-approve": { status: 200, json: { ok: true, message: "Jóváhagyva (reakció)." } } }),
  C("reakcio horgony nelkul -> nema (no_anchor uzenettel is)", r(41, K, 1760000200, [em("👍")], [em("👍"), em("🔥")]),
    { "draft-approve": { status: 404, json: { ok: false, reason: "no_anchor", message: "nem latszik" } } }),
  C("custom_emoji reakcio", r(42, J, 1760000300, [], [{ type: "custom_emoji", custom_emoji_id: "5" }]), { "draft-approve": NA }),
  C("fizetos (paid) reakcio", r(43, J, 1760000400, [], [{ type: "paid" }]), { "draft-approve": NA }),
  C("ugy-lablecre reply, horgony nincs -> ugy-uzenet, nema",
    { message: m({ message_id: 51, text: "Írd meg neki a levelet.", reply_to_message: botMsg(`Megjött a forgalmi.\n\n${FOOT}`) }) },
    { "draft-approve": NA, "case-message": OK }),
  C("ugy-lablecre reply, nem jovahagyas + tul regi -> a ket mondat egy uzenetben",
    { message: m({ message_id: 52, text: "a második bekezdést írd át", reply_to_message: botMsg(`Kérdés.\n${FOOT}`) }) },
    { "draft-approve": { status: 422, json: { ok: false, reason: "not_an_approval", message: "Ezt nem vettem jóváhagyásnak." } },
      "case-message": { status: 409, json: { ok: false, reason: "too_old", message: "Ez túl régi." } } }),
  C("ugy-lablecre reply, de nem a kijelolt kuldotol -> csak draft",
    { message: m({ message_id: 53, from: { id: K, first_name: "Masik" }, text: "Írd meg.", reply_to_message: botMsg(`X.\n${FOOT}`) }) },
    { "draft-approve": NA }),
  C("bot-uzenetre reply lablec nelkul, keresnek latszik -> Melyik ugyre?",
    { message: m({ message_id: 54, text: "írd meg", reply_to_message: botMsg("Megnéztem a portált.") }) }, { "draft-approve": NA }),
  C("bot-uzenetre reply lablec nelkul, nem keres -> nema",
    { message: m({ message_id: 55, text: "Köszi, megvan.", reply_to_message: botMsg("Megnéztem a portált.") }) }, { "draft-approve": NA }),
  C("ket ugyet emlito bot-uzenet -> nem kotheto, Melyik ugyre?",
    { message: m({ message_id: 56, text: "Írd meg neki.", reply_to_message: botMsg(`Lásd https://admin.example.test/ugyek/ugy-7 is.\n\n${FOOT}`) }) },
    { "draft-approve": NA }),
  C("listaoldal-lablec (/ugyek/tipus) nem ugy -> Melyik ugyre?",
    { message: m({ message_id: 57, text: "Írd meg neki.", reply_to_message: botMsg("Lista.\nÜgy: https://admin.example.test/ugyek/tipus/ugyfel") }) },
    { "draft-approve": NA }),
  C("kodolt listaoldal (tipu%73) sem ugy -> Melyik ugyre?",
    { message: m({ message_id: 66, text: "Írd meg neki.", reply_to_message: botMsg("Lista.\nÜgy: https://admin.example.test/ugyek/tipu%73") }) },
    { "draft-approve": NA }),
  C("/ugyek/tipus/ugyek/ugy-9 lablec -> a fork szerint nem kotheto",
    { message: m({ message_id: 67, text: "Írd meg neki.", reply_to_message: botMsg("Lista.\nÜgy: https://admin.example.test/ugyek/tipus/ugyek/ugy-9") }) },
    { "draft-approve": NA, "case-message": OK }),
  C("mely-link ugyanarra az ugyre nem ketertelmu -> ugy-uzenet",
    { message: m({ message_id: 58, text: "Küldd el.", reply_to_message: botMsg(`Vár: https://admin.example.test/ugyek/ugy-42#level\n${FOOT}`) }) },
    { "draft-approve": NA, "case-message": OK }),
  C("nem a bot uzenetere adott reply lablec-szoveggel -> csak draft",
    { message: m({ message_id: 59, text: "Írd meg.", reply_to_message: { message_id: 45, from: { id: K }, text: `idézet\n${FOOT}` } }) },
    { "draft-approve": NA }),
  C("tobbsoros, vezerlo- es zero-width karakteres reply -> egy sorba vonva",
    { message: m({ message_id: 64, text: "Írd meg neki:\n\n  első pont\tkettő​\r\nvége ", reply_to_message: botMsg(`Kérdés.\n${FOOT}`) }) },
    { "draft-approve": NA, "case-message": OK }),
  C("hosszu (2000 karakteres) reply -> 1500-nal vagva",
    { message: m({ message_id: 65, text: "Írd meg " + "ábc ".repeat(498), reply_to_message: botMsg(`Kérdés.\n${FOOT}`) }) },
    { "draft-approve": NA, "case-message": OK }),
  C("idegen chat -> semmi", { message: m({ message_id: 60, chat: { id: -777, type: "group" }, from: { id: 333 }, reply_to_message: botMsg(FOOT) }) }),
  C("bot kuldo -> semmi", { message: m({ message_id: 61, from: { id: 555, is_bot: true }, reply_to_message: botMsg(FOOT) }) }),
  C("reply nelkuli uzenet -> semmi", { message: m({ message_id: 62, text: "írd meg" }) }),
  C("szerkesztett reply -> semmi", { edited_message: m({ message_id: 63, reply_to_message: botMsg(FOOT) }) }),
];

// ---- gyerek-oldal (--import): a fetch-csonk; a fork main()-je hajtja ----
const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
function child() {
  const cases = CASES, out = cases.map(() => ({ requests: [], replies: [] }));
  let idx = -1, inflight = 0, last = Date.now();
  const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  globalThis.fetch = async (url, opts = {}) => {
    const u = new URL(url);
    inflight++;
    try {
      if (u.hostname === "api.example.test") {
        const endpoint = u.pathname.split("/").pop();
        out[idx].requests.push({ endpoint, headers: Object.keys(opts.headers).map((h) => h.toLowerCase()).sort(), rawBody: opts.body });
        const v = cases[idx].responses[endpoint];
        if (!v) throw new Error(`varatlan hivas: ${endpoint}`);
        return json(v.status, v.json);
      }
      const method = u.pathname.split("/").pop(), q = u.searchParams;
      if (method === "getMe") return json(200, { ok: true, result: { id: BOT, is_bot: true, username: "teszt_bot" } });
      if (method === "sendMessage" && q.has("reply_to_message_id")) {
        out[idx].replies.push({ chat_id: q.get("chat_id"), reply_to_message_id: Number(q.get("reply_to_message_id")), text: q.get("text") });
      }
      if (method !== "getUpdates" || q.get("offset") === "-1") return json(200, { ok: true, result: method === "getUpdates" ? [] : { message_id: 9000 } });
      inflight--;
      while (inflight > 0 || Date.now() - last < 400) await sleep(25); // az elozo eset elcsendesedett
      inflight++;
      if (++idx >= cases.length) { writeFileSync(process.env.REC_OUT, JSON.stringify(out)); process.exit(0); }
      return json(200, { ok: true, result: [{ update_id: idx + 1, ...cases[idx].update }] });
    } finally { inflight--; last = Date.now(); }
  };
}

// ---- szulo-oldal: a gyerek inditasa izolalt HOME/PATH-szal, majd a fixtura ----
async function main() {
  const [forkDir, outPath] = process.argv.slice(2);
  if (!forkDir || !outPath) { console.error("hasznalat: <fork-hid-konyvtar> <kimenet.json>"); process.exit(64); }
  const tmp = tempDir("whrec-"), raw = join(tmp, "raw.json");
  const res = spawnSync(process.execPath, ["--import", fileURLToPath(import.meta.url), join(resolve(forkDir), "bridge.mjs")], {
    env: { PATH: tmp, HOME: tmp, REC_CHILD: "1", REC_OUT: raw, TELEGRAM_BOT_TOKEN: "rec", TELEGRAM_GROUP_CHAT_ID: String(GROUP),
      TELEGRAM_ALLOWLIST_IDS: `${J},${K}`, TMUX_SESSION: "nincs-ilyen-rec", BRIDGE_STATE_DIR: join(tmp, "state"),
      BRIDGE_REQUIRE_MENTION: "false", PARTNER_CASE_API: "https://api.example.test", PARTNER_BRIDGE_TOKEN: TOKEN,
      ANNA_TELEGRAM_ID: String(J) }, encoding: "utf8", timeout: 120_000 });
  if (res.status !== 0) { console.error(res.stderr || res.error); process.exit(1); }
  const got = JSON.parse(readFileSync(raw, "utf8"));
  const { MELYIK_UGYRE } = await import(join(resolve(forkDir), "lib", "jovahagyas.mjs"));
  const fixture = { _comment: "A Partner-fork hidjabol rogzitve (kitalalt id-k, token nelkul).",
    _recorder: "node bridge/test/fixtures/webhook-paritas-recorder.mjs <fork-hid-konyvtar> bridge/test/fixtures/webhook-paritas.json",
    bot: { id: BOT, username: "teszt_bot" }, group: String(GROUP), allow: [String(J), String(K)], kijelolt_kuldo: String(J),
    nofooter_reply: MELYIK_UGYRE, cases: CASES.map((c, i) => ({ ...c, expected: got[i] })) };
  const s = JSON.stringify(fixture, null, 1);
  if (s.includes(TOKEN)) throw new Error("token a fixturaban");
  writeFileSync(outPath, s + "\n");
  for (const c of fixture.cases) console.log(`${c.name}: ${c.expected.requests.map((x) => x.endpoint).join("+") || "-"} | valasz=${c.expected.replies.length}`);
}

if (process.env.REC_CHILD === "1") child();
else if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
