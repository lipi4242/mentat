// send.mjs darabolva (H1): 4096 felett (i/n) darabok sorban, az elso
// nem-confirmed darabnal megall; --html 4096 felett exit 4, 0 keres.
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

// script: keresenkenti mod ("ok" | "fail" | "hang"); a vegen tul "ok".
function fakeTelegram(script = []) {
  return new Promise((resolve) => {
    const bodies = [];
    const srv = createServer((req, res) => {
      let body = "";
      req.on("data", (c) => { body += c; });
      req.on("end", () => {
        bodies.push(JSON.parse(body || "{}"));
        const mode = script[bodies.length - 1] || "ok";
        if (mode === "hang") return;
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(mode === "ok"
          ? { ok: true, result: { message_id: 100 + bodies.length } }
          : { ok: false, error_code: 400, description: "Bad Request: valami" }));
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve({
      url: `http://127.0.0.1:${srv.address().port}`, bodies,
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

// ~9000 kodegyseg, ekezet + emoji + sortores
function longText() {
  let s = "";
  for (let i = 0; s.length < 9000; i++) s += "árvíztűrő 🙂 " + (i % 10 === 9 ? "\n" : "");
  return s.slice(0, 9000).replace(/[\uD800-\uDBFF]$/, "");
}

test("9000 kar -> 3 darab, reply_to csak az elson, 3 intent part-tal, 3 confirmed", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sc-");
  const text = longText();
  const r = await runSend(["--chat", "-100", "--reply-to", "7", "--", text],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  tg.close();
  assert.equal(r.code, 0, r.stderr);
  assert.equal(tg.bodies.length, 3);
  tg.bodies.forEach((b, i) => {
    assert.ok(b.text.length <= 4096, `darab ${i + 1}: ${b.text.length}`);
    assert.ok(b.text.startsWith(`(${i + 1}/3) `));
  });
  assert.equal(tg.bodies[0].reply_to_message_id, 7);
  assert.equal(tg.bodies[1].reply_to_message_id, undefined);
  assert.equal(tg.bodies[2].reply_to_message_id, undefined);
  assert.equal(tg.bodies.map((b) => b.text.replace(/^\(\d\/3\) /, "")).join(""), text);
  assert.deepEqual(r.stdout.trim().split("\n"), ["101", "102", "103"]);
  const rows = readDay(dir, today());
  const intents = rows.filter((x) => x.type === "intent");
  assert.deepEqual(intents.map((x) => x.part), ["1/3", "2/3", "3/3"]);
  assert.equal(intents[0].reply_to, 7);
  assert.equal(intents[1].reply_to, undefined);
  assert.deepEqual(resolveSends(rows).map((s) => s.status), ["confirmed", "confirmed", "confirmed"]);
});

test("2. darab ok:false -> a 3. nem megy, exit 1, stderr nevez", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram(["ok", "fail", "ok"]);
  const dir = tempDir("sc-");
  const r = await runSend(["--chat", "-100", "--", longText()],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  tg.close();
  assert.equal(r.code, 1, r.stderr);
  assert.equal(tg.bodies.length, 2, "a 3. keres nem erkezhet meg");
  assert.match(r.stderr, /darab 2\/3 failed/);
  assert.match(r.stderr, /kiment: 1\/3/);
  assert.match(r.stderr, /nem ment: 2\/3, 3\/3/);
  assert.deepEqual(r.stdout.trim().split("\n"), ["101"]);
});

test("2. darab timeout -> exit 5, harom lista, stdout csak a confirmed", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram(["ok", "hang", "ok"]);
  const dir = tempDir("sc-");
  const r = await runSend(["--chat", "-100", "--", longText()],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir, SUBETHA_SEND_TIMEOUT_MS: "300" });
  tg.close();
  assert.equal(r.code, 5, r.stderr);
  assert.equal(tg.bodies.length, 2);
  assert.match(r.stderr, /darab 2\/3 unknown/);
  assert.match(r.stderr, /kiment: 1\/3; bizonytalan: 2\/3; nem probalt: 3\/3/);
  assert.deepEqual(r.stdout.trim().split("\n"), ["101"]);
});

test("--html es 5000 karakter -> exit 4, 0 keres", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram();
  const dir = tempDir("sc-");
  const r = await runSend(["--chat", "-100", "--html", "--", "x".repeat(5000)],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  tg.close();
  assert.equal(r.code, 4, r.stderr);
  assert.equal(tg.bodies.length, 0);
  assert.match(r.stderr, /--html 4096 felett/);
  assert.deepEqual(readDay(dir, today()), []);
});

test("egydarabos uzenet hibaja pontosan: sendMessage failed: <error>, dupla elotag nelkul", { timeout: 15000 }, async () => {
  const tg = await fakeTelegram(["fail"]);
  const dir = tempDir("sc-");
  const r = await runSend(["--chat", "-100", "--", "rovid"],
    { SUBETHA_TELEGRAM_API: tg.url, BRIDGE_INBOX_DIR: dir });
  tg.close();
  assert.equal(r.code, 1, r.stderr);
  assert.match(r.stderr, /^sendMessage failed: /m);
  assert.doesNotMatch(r.stderr, /sendMessage sendMessage/);
  assert.doesNotMatch(r.stderr, /darab|kiment|nem ment/);
});
