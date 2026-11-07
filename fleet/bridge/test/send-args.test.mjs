// Szigoru argv (H3): ismeretlen kapcsolo exit 64 Telegram-hivas nelkul;
// --instance elavultkent elfogadva (2.0.x kompat), notice sor a naploba.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, UsageError } from "../lib/send-args.mjs";
import { parseArgs as reexported } from "../send.mjs";
import { readDay, makeRow } from "../lib/delivery-log.mjs";
import { logNotice } from "../lib/notice.mjs";

const SEND = join(dirname(fileURLToPath(import.meta.url)), "..", "send.mjs");
const today = () => new Date().toISOString().slice(0, 10);

function fakeTelegram() {
  return new Promise((resolve) => {
    const bodies = [];
    let onRequest = () => {};
    const seen = new Promise((r) => { onRequest = r; });
    const srv = createServer((req, res) => {
      let body = "";
      req.on("data", (c) => { body += c; });
      req.on("end", () => {
        const b = JSON.parse(body || "{}");
        bodies.push(b);
        onRequest({ url: req.url, body: b });
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify({ ok: true, result: { message_id: 77 } }));
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve({
      url: `http://127.0.0.1:${srv.address().port}`, seen, bodies,
      close: () => { srv.closeAllConnections?.(); srv.close(); },
    }));
  });
}

function runSend(args, env) {
  const child = spawn(process.execPath, [SEND, ...args], {
    env: { PATH: process.env.PATH, TELEGRAM_BOT_TOKEN: "t", ...env },
  });
  let stdout = "", stderr = "";
  child.stdout.on("data", (c) => { stdout += c; });
  child.stderr.on("data", (c) => { stderr += c; });
  return new Promise((r) => child.on("close", (code) => r({ code, stdout, stderr })));
}

const within = (p, ms) => Promise.race([p.then(() => true), new Promise((r) => setTimeout(() => r(false), ms))]);

test("ismeretlen kapcsolo: UsageError, code 64, megnevezi", () => {
  assert.throws(() => parseArgs(["--chat", "1", "--bogus", "x", "--", "t"]),
    (e) => e instanceof UsageError && e.code === 64 && /--bogus/.test(e.message));
});

test("--instance: elfogadva, ertek eldobva, deprecated jelolve", () => {
  const a = parseArgs(["--chat", "1", "--instance", "kata", "--", "hello"]);
  assert.equal(a.text, "hello");
  assert.deepEqual(a.deprecated, ["--instance"]);
});

test("a send.mjs re-exportja ugyanaz a parseArgs", () => {
  assert.equal(reexported, parseArgs);
});

test("ertek-kapcsolo erteke nem lehet --kapcsolo (UsageError, code 1)", () => {
  for (const f of ["--chat", "--reply-to", "--react", "--message", "--why", "--instance"]) {
    assert.throws(() => parseArgs([f, "--html", "--", "t"]),
      (e) => e instanceof UsageError && e.code === 1 && e.message.includes(f), f);
  }
});

test("folyamat: --bogus -> exit 64, a Telegram 0 kerest kap", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sa-");
  const r = await runSend(["--chat", "1", "--bogus", "x", "--", "szoveg"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: dir });
  const hit = await within(tg.seen, 300); tg.close();
  assert.equal(r.code, 64, r.stderr);
  assert.match(r.stderr, /--bogus/);
  assert.equal(hit, false, "nem mehetett Telegram-keres");
});

test("folyamat: --chat --html -> exit 1, a Telegram 0 kerest kap", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sa-");
  const r = await runSend(["--chat", "--html", "--", "szoveg"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: dir });
  const hit = await within(tg.seen, 300); tg.close();
  assert.equal(r.code, 1, r.stderr);
  assert.equal(hit, false);
});

test("folyamat: -- utan a --bogus szo szerint szoveg, exit 0", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sa-");
  const r = await runSend(["--chat", "1", "--", "--bogus", "x"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: dir });
  tg.close();
  assert.equal(r.code, 0, r.stderr);
  assert.equal(tg.bodies[0].text, "--bogus x");
});

test("folyamat: --instance kata -> text=hello, stderr figyelmeztet, notice sor", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sa-");
  const r = await runSend(["--chat", "1", "--instance", "kata", "--", "hello"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_STATE_DIR: dir });
  tg.close();
  assert.equal(r.code, 0, r.stderr);
  assert.equal(tg.bodies[0].text, "hello");
  assert.match(r.stderr, /--instance elavult/);
  const rows = readDay(join(dir, "telegram-inbox"), today());
  const n = rows.filter((x) => x.type === "notice" && x.event === "deprecated_flag");
  assert.equal(n.length, 1);
  assert.equal(n[0].detail, "--instance");
});

test("notice sor: event kotelezo; logNotice sosem dob", () => {
  assert.throws(() => makeRow({ type: "notice" }), /notice event nelkul/);
  assert.equal(logNotice(null, "deprecated_flag").ok, false);
  assert.equal(logNotice("/x", "").ok, false);
});

test("--reply-to 0 es tul nagy --message: UsageError (code 1), nem pontatlan szam", () => {
  for (const argv of [["--chat", "1", "--reply-to", "0", "--", "x"],
    ["--chat", "1", "--react", "👍", "--message", "99999999999999999999"],
    ["--chat", "1", "--reply-to", "00", "x"]]) {
    assert.throws(() => parseArgs(argv), (e) => e instanceof UsageError && e.code === 1, argv.join(" "));
  }
  assert.equal(parseArgs(["--chat", "1", "--reply-to", "9007199254740991", "x"]).replyTo, 9007199254740991);
});
