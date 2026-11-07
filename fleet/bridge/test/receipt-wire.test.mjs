// Erkezes-nyugta (3.2) bekotese: deliverer-horgok, config-kapcsolo, a hid-drot.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createDeliverer } from "../lib/deliverer.mjs";
import { loadConfig } from "../lib/config.mjs";
import { createReceiptWire } from "../lib/receipt-wire.mjs";

const LINE = "[Telegram inbound | J id=1 | chat=-100 | msg=7]: x";
const ENV = { TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "1",
  TMUX_SESSION: "s", HOME: "/h" };

function deliverer(dir, inject, hooks) {
  return createDeliverer({ session: "s", pendingFile: join(dir, "p.json"), maxPending: 10,
    pendingAlertMs: 1e9, healthFile: join(dir, "h.json"), label: "x", inject, ...hooks });
}

test("deliverer: sikertelen inject -> pending, onInjected nem hivodik; retryPending utan egyszer", async () => {
  const dir = tempDir("rw-");
  let n = 0; const calls = [];
  const failThenOk = () => (n++ === 0 ? { ok: false, error: "x" } : { ok: true });
  const d = deliverer(dir, failThenOk, {
    beforeInject: (l) => calls.push(["before", l]), onInjected: (l) => calls.push(["on", l]) });
  d.deliver(LINE);
  assert.deepEqual(calls, [["before", LINE]]);
  await d.retryPending();
  assert.deepEqual(calls, [["before", LINE], ["before", LINE], ["on", LINE]]);
});

test("deliverer: horog-hiba sosem dob, a kezbesites megy", () => {
  const dir = tempDir("rw-");
  const d = deliverer(dir, () => ({ ok: true }), {
    beforeInject: () => { throw new Error("a"); }, onInjected: () => { throw new Error("b"); } });
  d.deliver(LINE);
  assert.equal(d.depth(), 0);
});

test("config: BRIDGE_RECEIPT nelkul KI; =1-gyel BE, utvonalak", () => {
  const off = loadConfig({ ...ENV, BRIDGE_STATE_DIR: "/st" });
  assert.equal(off.receipt, false);
  assert.equal(loadConfig({ ...ENV, BRIDGE_STATE_DIR: "/st", BRIDGE_RECEIPT: "true" }).receipt, false);
  const on = loadConfig({ ...ENV, BRIDGE_STATE_DIR: "/st", BRIDGE_RECEIPT: "1" });
  assert.equal(on.receipt, true);
  assert.equal(on.sessionIdFile, "/st/session.id");
  assert.equal(on.transcriptRoot, "/h/.claude/projects");
  assert.equal(on.receiptFile, "/st/telegram-state/receipts.json");
  const o2 = loadConfig({ ...ENV, BRIDGE_STATE_DIR: "/st", BRIDGE_TRANSCRIPT_ROOT: "/tr",
    BRIDGE_SESSION_ID_FILE: "/sid" });
  assert.equal(o2.transcriptRoot, "/tr");
  assert.equal(o2.sessionIdFile, "/sid");
});

test("wire KI: nincs horog, nincs receipts-fajl", () => {
  const dir = tempDir("rw-");
  const w = createReceiptWire(loadConfig({ ...ENV, BRIDGE_STATE_DIR: dir }), { tg: async () => {} });
  assert.deepEqual(w.hooks, {});
  w.start(); w.check();
  assert.equal(w.depth(), 0);
  assert.equal(readdirSync(dir).length, 0);
});

test("wire BE: deliver -> rogzites; ket deadline utan unconfirmed notice + riasztas + egy 😨 (a ⚠️ nem engedett Telegram-reakcio)", async () => {
  const dir = tempDir("rw-");
  mkdirSync(join(dir, "tr", "-p"), { recursive: true });
  writeFileSync(join(dir, "session.id"), "sid\n");
  writeFileSync(join(dir, "tr", "-p", "sid.jsonl"), "");
  const cfg = loadConfig({ ...ENV, BRIDGE_STATE_DIR: dir, BRIDGE_RECEIPT: "1", BRIDGE_TRANSCRIPT_ROOT: join(dir, "tr") });
  const tgCalls = [], alerts = [], injected = [];
  const clock = { t: 5_000_000 };
  const w = createReceiptWire(cfg, { tg: async (m, p) => { tgCalls.push([m, p]); },
    alert: async (t) => alerts.push(t), now: () => clock.t });
  const d = deliverer(dir, (s, l) => { injected.push(l); return { ok: true }; }, w.hooks);
  w.bind(d);
  d.deliver(LINE);
  d.deliver("[Telegram inbound | J id=1 | chat=-100 | reaction]: 👍 on message 7");
  assert.equal(w.depth(), 1);
  clock.t += 121_000; w.check();
  assert.deepEqual(injected.filter((l) => l === LINE).length, 2, "egy ujrainjektalas");
  clock.t += 121_000; w.check();
  clock.t += 121_000; w.check();
  await new Promise((r) => setImmediate(r));
  assert.equal(alerts.length, 1);
  assert.match(alerts[0], /msg=7/);
  assert.deepEqual(tgCalls, [["setMessageReaction",
    { chat_id: "-100", message_id: 7, reaction: [{ type: "emoji", emoji: "😨" }] }]]);
  const rows = readdirSync(join(dir, "telegram-inbox")).filter((f) => f.startsWith("delivery-"))
    .flatMap((f) => readFileSync(join(dir, "telegram-inbox", f), "utf8").trim().split("\n").map((l) => JSON.parse(l)));
  const notices = rows.filter((r) => r.type === "notice");
  assert.equal(notices.length, 1);
  assert.equal(notices[0].event, "inbound_unconfirmed");
  assert.equal(notices[0].chat_id, "-100");
  assert.equal(notices[0].msg_id, "7");
});

function wired(dir, { transcript = true } = {}) {
  mkdirSync(join(dir, "tr", "-p"), { recursive: true });
  writeFileSync(join(dir, "session.id"), "sid\n");
  if (transcript) writeFileSync(join(dir, "tr", "-p", "sid.jsonl"), "");
  const cfg = loadConfig({ ...ENV, BRIDGE_STATE_DIR: dir, BRIDGE_RECEIPT: "1", BRIDGE_TRANSCRIPT_ROOT: join(dir, "tr") });
  const out = { tgCalls: [], alerts: [], clock: { t: 5_000_000 } };
  out.w = createReceiptWire(cfg, { tg: async (m, p) => { out.tgCalls.push([m, p]); },
    alert: async (t) => out.alerts.push(t), now: () => out.clock.t });
  out.d = deliverer(dir, () => ({ ok: true }), out.w.hooks);
  out.w.bind(out.d);
  return out;
}
const notices = (dir) => readdirSync(join(dir, "telegram-inbox")).filter((f) => f.startsWith("delivery-"))
  .flatMap((f) => readFileSync(join(dir, "telegram-inbox", f), "utf8").trim().split("\n").map((l) => JSON.parse(l)))
  .filter((r) => r.type === "notice");

test("wire: nincs transzkript, ket uzenet -> 2 notice, 1 riasztas, 0 reakcio", async () => {
  const dir = tempDir("rw-");
  const o = wired(dir, { transcript: false });
  o.d.deliver(LINE);
  o.d.deliver("[Telegram inbound | J id=1 | chat=-100 | msg=8]: y");
  o.clock.t += 121_000; o.w.check();
  await new Promise((r) => setImmediate(r));
  const n = notices(dir);
  assert.equal(n.length, 2);
  assert.ok(n.every((r) => r.event === "inbound_unconfirmed" && r.detail === "no transcript"));
  assert.equal(o.alerts.length, 1);
  assert.equal(o.tgCalls.length, 0);
});

test("wire: megjelent sor -> inbound_confirmed notice, nincs riasztas", async () => {
  const dir = tempDir("rw-");
  const o = wired(dir);
  o.d.deliver(LINE);
  writeFileSync(join(dir, "tr", "-p", "sid.jsonl"),
    JSON.stringify({ type: "user", message: { role: "user", content: LINE } }) + "\n");
  o.w.check();
  await new Promise((r) => setImmediate(r));
  const n = notices(dir);
  assert.equal(n.length, 1);
  assert.equal(n[0].event, "inbound_confirmed");
  assert.equal(n[0].msg_id, "7");
  assert.equal(o.alerts.length + o.tgCalls.length, 0);
});

test("wire: tobb stale egy koron belul -> EGY osszesito riasztas, 0 reakcio, notice soronkent", async () => {
  const dir = tempDir("rw-");
  const o = wired(dir);
  o.d.deliver(LINE);
  o.d.deliver("[Telegram inbound | J id=1 | chat=-100 | msg=8]: y");
  o.clock.t += 120_000 + 2 * 120_000 + 1;
  o.w.check();
  await new Promise((r) => setImmediate(r));
  assert.equal(o.alerts.length, 1);
  assert.match(o.alerts[0], /2 üzenet ellenőrizetlen maradt/);
  assert.match(o.alerts[0], /msg=7/);
  assert.match(o.alerts[0], /msg=8/);
  assert.equal(o.tgCalls.length, 0);
  const n = notices(dir);
  assert.equal(n.length, 2);
  assert.ok(n.every((r) => r.detail === "stale"));
});
