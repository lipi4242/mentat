// send.mjs a valodi folyamatkent: szandek ELORE, kimenet UTANA, osszeomlasnal
// / timeoutnal `unknown` — a naplo sosem hallgat egy elinditott kuldesrol.
// Egy helyi HTTP-szerver jatssza a Telegramot (SUBETHA_TELEGRAM_API).
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { readDay, resolveSends } from "../lib/delivery-log.mjs";

const SEND = join(dirname(fileURLToPath(import.meta.url)), "..", "send.mjs");
const today = () => new Date().toISOString().slice(0, 10);

// mode: "ok" | "fail" | "hang"
function fakeTelegram(mode) {
  return new Promise((resolve) => {
    let onRequest = () => {};
    const seen = new Promise((r) => { onRequest = r; });
    const srv = createServer((req, res) => {
      let body = "";
      req.on("data", (c) => { body += c; });
      req.on("end", () => {
        onRequest({ url: req.url, body: JSON.parse(body || "{}") });
        if (mode === "hang") return; // soha nem valaszol
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(mode === "ok"
          ? { ok: true, result: { message_id: 77 } }
          : { ok: false, error_code: 400, description: "Bad Request: chat not found" }));
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve({
      url: `http://127.0.0.1:${srv.address().port}`, seen,
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
  const done = new Promise((r) => child.on("close", (code, signal) => r({ code, signal, stdout, stderr })));
  return { child, done };
}

test("confirmed: szandek + kimenet message_id-vel, exit 0, stdout a message_id", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("ok");
  const dir = tempDir("sd-");
  const { done } = runSend(["--chat", "-100", "--reply-to", "7", "--", "szia"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  const r = await done; tg.close();
  assert.equal(r.code, 0, r.stderr);
  assert.equal(r.stdout.trim(), "77");
  const rows = readDay(dir, today());
  assert.deepEqual(rows.map((x) => x.type), ["intent", "outcome"]);
  assert.equal(rows[0].reply_to, 7);
  assert.equal(rows[0].text, "szia");
  const [s] = resolveSends(rows);
  assert.equal(s.status, "confirmed");
  assert.equal(s.message_id, 77);
});

test("failed: a Telegram ok:false -> failed kimenet, exit 1", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("fail");
  const dir = tempDir("sd-");
  const { done } = runSend(["--chat", "-100", "--", "x"], { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  const r = await done; tg.close();
  assert.equal(r.code, 1);
  const [s] = resolveSends(readDay(dir, today()));
  assert.equal(s.status, "failed");
  assert.match(s.error, /chat not found/);
});

test("timeout: a keres elment, valasz nincs -> unknown kimenet, exit 5", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("hang");
  const dir = tempDir("sd-");
  const { done } = runSend(["--chat", "-100", "--", "x"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir, SUBETHA_SEND_TIMEOUT_MS: "300" });
  const r = await done; tg.close();
  assert.equal(r.code, 5, r.stderr);
  const rows = readDay(dir, today());
  assert.deepEqual(rows.map((x) => x.type), ["intent", "outcome"]);
  assert.equal(resolveSends(rows)[0].status, "unknown");
});

test("osszeomlas a keres utan (SIGKILL): a szandek-sor ott van, a statusz unknown", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("hang");
  const dir = tempDir("sd-");
  const { child, done } = runSend(["--chat", "-100", "--reply-to", "9", "--", "x"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  await tg.seen;            // a keres mar a "Telegramnal" van
  child.kill("SIGKILL");
  const r = await done; tg.close();
  assert.equal(r.signal, "SIGKILL");
  const rows = readDay(dir, today());
  assert.deepEqual(rows.map((x) => x.type), ["intent"], "kimenet nincs, a szandek megvan");
  const [s] = resolveSends(rows);
  assert.equal(s.status, "unknown");
  assert.equal(s.has_outcome, false);
  assert.equal(s.reply_to, 9);
});

test("reakcio: ugyanaz a szandek/kimenet par, action=reaction, target_msg_id", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("ok");
  const dir = tempDir("sd-");
  const { done } = runSend(["--chat", "-100", "--react", "👍", "--message", "7"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  const r = await done; tg.close();
  assert.equal(r.code, 0, r.stderr);
  const [s] = resolveSends(readDay(dir, today()));
  assert.equal(s.action, "reaction");
  assert.equal(s.target_msg_id, 7);
  assert.equal(s.status, "confirmed");
});

test("naplo-hely ismeretlen: a kuldes megy, de exit 3 (hangos, nem nema)", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram("ok");
  const { done } = runSend(["--chat", "-100", "--", "x"], { SUBETHA_TELEGRAM_API: tg.url });
  const r = await done; tg.close();
  assert.equal(r.code, 3);
  assert.equal(r.stdout.trim(), "77");
  assert.match(r.stderr, /kezbesitesi naplo/);
});
