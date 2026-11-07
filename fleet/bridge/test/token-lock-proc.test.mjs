// H5 folyamatszinten: valodi versengo folyamatok es ket valodi `node bridge.mjs`.
// A hamis Telegram getMe-re valaszol, getUpdates-re soha — igy a tmux-injekt
// sosem fut, tmux nem kell. A ket hid kulon URL-prefixet kap, ebbol latszik,
// melyik folyamat hivott.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { lockName } from "../lib/token-lock.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const BRIDGE = join(HERE, "..", "bridge.mjs");
const LOCK = join(HERE, "..", "lib", "token-lock.mjs");
const bridgeEnv = (root, api, extra) => ({ TELEGRAM_BOT_TOKEN: TOK, TMUX_SESSION: "x",
  TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1", BRIDGE_STATE_DIR: join(root, "s"),
  BRIDGE_LOCK_DIR: join(root, "locks"), HOME: root, SUBETHA_TELEGRAM_API: api, ...extra });
const TOK = "TOKEN-sekret-42";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fakeTelegram() {
  const hits = [];
  const srv = createServer((req, res) => {
    hits.push(req.url);
    if (!req.url.endsWith("/getMe")) return; // getUpdates: soha nem valaszol
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ ok: true, result: { id: 1, username: "b" } }));
  });
  return new Promise((r) => srv.listen(0, "127.0.0.1", () => r({
    url: `http://127.0.0.1:${srv.address().port}`, hits,
    close: () => { srv.closeAllConnections?.(); srv.close(); },
  })));
}

function run(args, env) {
  const child = spawn(process.execPath, args, { env: { PATH: process.env.PATH, ...env } });
  let out = "", err = "";
  child.stdout.on("data", (c) => { out += c; });
  child.stderr.on("data", (c) => { err += c; });
  const done = new Promise((r) => child.on("close", (code, signal) => r({ code, signal, out, err })));
  return { child, done };
}

async function kill(p) {
  if (p.child.exitCode !== null || p.child.signalCode !== null) return p.done;
  p.child.kill("SIGTERM");
  const t = setTimeout(() => p.child.kill("SIGKILL"), 2000);
  const r = await p.done;
  clearTimeout(t);
  return r;
}

async function waitFor(pred, ms = 5000) {
  for (let t = 0; t < ms; t += 50) { if (pred()) return true; await sleep(50); }
  return false;
}

test("8 versengo folyamat ugyanarra a zarra: pontosan egy ok", { timeout: 20000 }, async () => {
  const lockDir = join(tempDir("tlp-"), "locks");
  const code = `import(${JSON.stringify(LOCK)}).then(async (m) => {
    const l = m.acquireTokenLock({ lockDir: ${JSON.stringify(lockDir)}, token: "T" });
    console.log(l.ok ? "OK" : "HELD"); await new Promise((r) => setTimeout(r, 1500)); })`;
  // A "bridge.mjs" argv-jel: Linuxon a /proc cmdline-ellenorzes igy a gyereket
  // elo hidnak latja — a valodi alapertelmezett pidAlive fut, nem egy kill-only.
  const ps = Array.from({ length: 8 }, () => run(["-e", code, "bridge.mjs"], {}));
  const rs = await Promise.all(ps.map((p) => p.done));
  const outs = rs.map((r) => r.out.trim());
  assert.equal(outs.filter((o) => o === "OK").length, 1, JSON.stringify(rs));
  assert.equal(outs.filter((o) => o === "HELD").length, 7, JSON.stringify(rs));
});

test("masodik hid ugyanarra a tokenre: exit 75, 0 Telegram-keres; az elso kilepeskor torol", { timeout: 30000 }, async () => {
  const tg = await fakeTelegram();
  const root = tempDir("tlb-");
  const lockDir = join(root, "locks");
  const env = (who, extra = {}) => ({
    TELEGRAM_BOT_TOKEN: TOK, TMUX_SESSION: "x", TELEGRAM_GROUP_CHAT_ID: "-1",
    TELEGRAM_ALLOWLIST_IDS: "1", BRIDGE_STATE_DIR: join(root, who), BRIDGE_LOCK_DIR: lockDir, HOME: root,
    SUBETHA_TELEGRAM_API: `${tg.url}/${who}`, ...extra,
  });
  const lockPath = join(lockDir, lockName(TOK));
  const a = run([BRIDGE], env("a"));
  let b;
  try {
    assert.ok(await waitFor(() => existsSync(lockPath)), "az elso hid zarja nem jelent meg");
    assert.equal(JSON.parse(readFileSync(lockPath, "utf8")).pid, a.child.pid);
    b = run([BRIDGE], env("b"));
    const t0 = Date.now();
    const rb = await b.done;
    assert.equal(rb.code, 75, rb.err);
    assert.ok(Date.now() - t0 < 5000);
    assert.match(rb.err, /token-zár foglalt/);
    assert.equal(rb.err.includes(TOK), false); // a token nem szivarog a hibasorba
    assert.equal(tg.hits.filter((u) => u.startsWith("/b/")).length, 0, JSON.stringify(tg.hits));
    assert.ok(await waitFor(() => tg.hits.some((u) => u.startsWith("/a/"))), "az elso hid nem hivott");
    const ra = await kill(a);
    assert.equal(ra.code, 0, ra.err);
    assert.equal(existsSync(lockPath), false, "a tulajdonos kilepeskor nem torolte a zarat");
  } finally {
    await kill(a);
    if (b) await kill(b);
    tg.close();
  }
});

test("elvett zar: a tulajdonos-ellenorzes exit 75-tel allitja le, az idegen zar marad", { timeout: 20000 }, async () => {
  const tg = await fakeTelegram();
  const root = tempDir("tls-");
  const lockPath = join(root, "locks", lockName(TOK));
  const a = run([BRIDGE], bridgeEnv(root, tg.url, { BRIDGE_LOCK_CHECK_MS: "1000" }));
  try {
    assert.ok(await waitFor(() => existsSync(lockPath)));
    const foreign = JSON.stringify({ pid: 4242, nonce: "masik", started_at: 1 });
    writeFileSync(lockPath, foreign);
    const t = setTimeout(() => a.child.kill("SIGKILL"), 5000);
    const r = await a.done;
    clearTimeout(t);
    assert.equal(r.code, 75, r.err);
    assert.match(r.err, /token-zár elveszett/);
    assert.equal(readFileSync(lockPath, "utf8"), foreign);
  } finally { await kill(a); tg.close(); }
});

test("irhatatlan zar-konyvtar: exit 75, egysoros FATAL, nincs stack trace, nincs Telegram", { timeout: 20000 }, async () => {
  const tg = await fakeTelegram();
  const root = tempDir("tlw-");
  writeFileSync(join(root, "fajl"), "x"); // konyvtar helyett fajl: rootkent is hibazik
  const r = await run([BRIDGE], bridgeEnv(root, tg.url, { BRIDGE_LOCK_DIR: join(root, "fajl", "locks") })).done;
  tg.close();
  assert.equal(r.code, 75, r.err);
  assert.match(r.err, /FATAL: token-zár könyvtár nem írható \(.*fajl\/locks\)/);
  assert.equal(/\n\s+at /.test(r.err), false, r.err);
  assert.equal(tg.hits.length, 0);
});
