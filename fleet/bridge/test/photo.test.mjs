import test from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, readFileSync } from "node:fs";
import { tempDir } from "./tmp.mjs";
import { join } from "node:path";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, USAGE } from "../send.mjs";
import { readDay } from "../lib/delivery-log.mjs";
import {
  checkCaption, checkPhotoFile, buildPhotoForm, MAX_CAPTION, MAX_PHOTO_BYTES,
} from "../lib/photo.mjs";

const dir = tempDir("photo-");
const png = join(dir, "kartya.png");
writeFileSync(png, Buffer.from([0x89, 0x50, 0x4e, 0x47]));

test("parseArgs: a regi alak valtozatlan (nincs photo/caption kulcs)", () => {
  const a = parseArgs(["--chat", "42", "hello"]);
  assert.ok(!("photo" in a) && !("caption" in a) && !("captionStdin" in a));
});

test("parseArgs: --photo + --caption + --reply-to + --instance", () => {
  const a = parseArgs(["--chat", "42", "--photo", "a.png", "--caption", "szia", "--reply-to", "7", "--instance", "demo"]);
  assert.equal(a.photo, "a.png");
  assert.equal(a.caption, "szia");
  assert.equal(a.replyTo, 7);
  assert.deepEqual(a.deprecated, ["--instance"]); // elavult: elfogadva, eldobva
});

test("parseArgs: --caption-stdin", () => {
  assert.equal(parseArgs(["--chat", "1", "--photo", "a.png", "--caption-stdin"]).captionStdin, true);
});

test("parseArgs: --photo ertek nelkul hangos hiba", () => {
  assert.throws(() => parseArgs(["--chat", "1", "--photo"]), /--photo requires a value/);
});

test("parseArgs: tiltott kombinaciok", () => {
  assert.throws(() => parseArgs(["--chat", "1", "--photo", "a.png", "szoveg"]), /cannot be combined/);
  assert.throws(() => parseArgs(["--chat", "1", "--photo", "a.png", "--text-stdin"]), /cannot be combined/);
  assert.throws(() => parseArgs(["--chat", "1", "--photo", "a.png", "--react", "x"]), /cannot be combined/);
  assert.throws(() => parseArgs(["--chat", "1", "--photo", "a.png", "--html"]), /cannot be combined/);
  assert.throws(() => parseArgs(["--chat", "1", "--photo", "a.png", "--caption", "x", "--caption-stdin"]), /mutually exclusive/);
  assert.throws(() => parseArgs(["--chat", "1", "--caption", "x"]), /require --photo/);
});

test("USAGE emliti a --photo modot", () => {
  assert.match(USAGE, /--photo/);
  assert.match(USAGE, /--caption-stdin/);
});

test("checkCaption: 1024 még jó, 1025 elutasitva", () => {
  assert.equal(checkCaption("x".repeat(MAX_CAPTION)).ok, true);
  const r = checkCaption("x".repeat(MAX_CAPTION + 1));
  assert.equal(r.ok, false);
  assert.match(r.message, /semmi nem ment ki/);
  assert.equal(checkCaption("").ok, true);
});

test("checkCaption: UTF-16 egyseg — emojis caption a Telegram szerint szamol", () => {
  const emo = "😀".repeat(513); // 513 kodpont, de 1026 UTF-16 egyseg
  assert.equal([...emo].length, 513);
  const r = checkCaption(emo);
  assert.equal(r.len, 1026);
  assert.equal(r.ok, false);
  assert.equal(checkCaption("😀".repeat(512)).ok, true); // pont 1024 egyseg
});

test("checkPhotoFile: kiterjesztes, letezes, meret", () => {
  assert.equal(checkPhotoFile(png).type, "image/png");
  assert.throws(() => checkPhotoFile(join(dir, "x.gif")), /csak/);
  assert.throws(() => checkPhotoFile(join(dir, "nincs.png")), /nem letezik/);
  assert.throws(() => checkPhotoFile(dir + "/x.PNG", () => ({ isFile: () => true, size: MAX_PHOTO_BYTES + 1 })), /10 MB/);
  assert.equal(checkPhotoFile(dir + "/x.JPG", () => ({ isFile: () => true, size: MAX_PHOTO_BYTES })).type, "image/jpeg");
  assert.throws(() => checkPhotoFile(dir + "/x.png", () => ({ isFile: () => true, size: 0 })), /ures/);
});

test("buildPhotoForm: mezok, nincs parse_mode, reply opcionalis", () => {
  const f = buildPhotoForm({ chatId: "42", path: png, caption: "[k] hi", replyTo: 7 });
  assert.equal(f.get("chat_id"), "42");
  assert.equal(f.get("caption"), "[k] hi");
  assert.equal(f.get("reply_to_message_id"), "7");
  assert.equal(f.get("parse_mode"), null);
  const file = f.get("photo");
  assert.equal(file.name, "kartya.png");
  assert.equal(file.type, "image/png");
  const g = buildPhotoForm({ chatId: "42", path: png, caption: "", replyTo: null });
  assert.equal(g.get("caption"), null);
  assert.equal(g.get("reply_to_message_id"), null);
});

// ---- folyamat-teszt: hamis Telegram, valodi send.mjs, kezbesitesi naplo ----
const today = () => new Date().toISOString().slice(0, 10);
const SEND = join(dirname(fileURLToPath(import.meta.url)), "..", "send.mjs");

function fakeTelegram() {
  return new Promise((resolve) => {
    const hits = [];
    const srv = createServer((req, res) => {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        hits.push({ url: req.url, ctype: req.headers["content-type"], body: Buffer.concat(chunks).toString("latin1") });
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify({ ok: true, result: { message_id: 88 } }));
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve({
      url: `http://127.0.0.1:${srv.address().port}`, hits,
      close: () => { srv.closeAllConnections?.(); srv.close(); },
    }));
  });
}

function runSend(args, env, stdin) {
  const child = spawn(process.execPath, [SEND, ...args], {
    env: { PATH: process.env.PATH, TELEGRAM_BOT_TOKEN: "t", ...env },
  });
  let stdout = "", stderr = "";
  child.stdout.on("data", (c) => { stdout += c; });
  child.stderr.on("data", (c) => { stderr += c; });
  child.stdin.end(stdin ?? "");
  return new Promise((r) => child.on("close", (code) => r({ code, stdout, stderr })));
}

test("folyamat: --photo + --caption-stdin -> sendPhoto multipart, message_id, naplo", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const state = tempDir("photo-state-");
  const r = await runSend(["--chat", "42", "--photo", png, "--caption-stdin", "--reply-to", "7"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: state }, "Döntési kártya");
  tg.close();
  assert.equal(r.code, 0, r.stderr);
  assert.equal(r.stdout.trim(), "88");
  assert.equal(tg.hits.length, 1);
  assert.match(tg.hits[0].url, /\/sendPhoto$/);
  assert.match(tg.hits[0].ctype, /^multipart\/form-data/);
  assert.match(tg.hits[0].body, /name="reply_to_message_id"\r\n\r\n7/);
  assert.doesNotMatch(tg.hits[0].body, /parse_mode/);
  const rows = readDay(join(state, "telegram-inbox"), today());
  assert.ok(rows.some((x) => x.type === "intent" && x.action === "message" && String(x.reply_to) === "7"));
  assert.ok(rows.some((x) => x.type === "outcome" && x.status === "confirmed" && x.message_id === 88));
});

test("folyamat: tul hosszu caption -> exit 1, 0 Telegram-keres, 0 naplosor", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const state = tempDir("photo-state-");
  const r = await runSend(["--chat", "42", "--photo", png, "--caption-stdin"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: state }, "x".repeat(1025));
  tg.close();
  assert.equal(r.code, 1);
  assert.match(r.stderr, /semmi nem ment ki/);
  assert.equal(tg.hits.length, 0);
  assert.equal(readDay(join(state, "telegram-inbox"), today()).length, 0);
});

test("folyamat: ismeretlen kiterjesztes -> exit 1, 0 keres", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const r = await runSend(["--chat", "42", "--photo", join(dir, "x.gif")], { SUBETHA_TELEGRAM_API: tg.url });
  tg.close();
  assert.equal(r.code, 1);
  assert.equal(tg.hits.length, 0);
});

test("folyamat: hosszusag-kapu a captionre: 901 karakter --why nelkul exit 4, semmi nem megy ki", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const state = tempDir("photo-state-");
  const env = { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: state, SUBETHA_LENGTH_GATE: "1" };
  const r = await runSend(["--chat", "42", "--photo", png, "--caption-stdin"], env, "x".repeat(901));
  assert.equal(r.code, 4, r.stderr);
  assert.equal(tg.hits.length, 0);
  assert.equal(readDay(join(state, "telegram-inbox"), today()).length, 0);
  // indokkal kimegy, az indok naplozodik, az intent-sor media:photo
  const ok = await runSend(["--chat", "42", "--photo", png, "--caption-stdin", "--why", "a teljes dontesi kartya szoveges osszefoglaloja"], env, "x".repeat(901));
  tg.close();
  assert.equal(ok.code, 0, ok.stderr);
  assert.equal(tg.hits.length, 1);
  assert.ok(readDay(join(state, "telegram-inbox"), today()).some((x) => x.type === "intent" && x.media === "photo"));
  assert.match(readFileSync(join(state, "length-gate.jsonl"), "utf8"), /"len":901/);
});

test("folyamat: emojis caption 1026 UTF-16 egyseg -> exit 1 (kapu a naplo ELOTT)", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const state = tempDir("photo-state-");
  const r = await runSend(["--chat", "42", "--photo", png, "--caption-stdin"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: state }, "😀".repeat(513));
  tg.close();
  assert.equal(r.code, 1);
  assert.equal(tg.hits.length, 0);
  assert.equal(readDay(join(state, "telegram-inbox"), today()).length, 0);
});
