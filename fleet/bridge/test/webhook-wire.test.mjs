// 3.1 jovahagyo webhook: ki jelolt (handlers) es az osszedrotozott hid.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHandlers } from "../lib/handlers.mjs";
import { loadConfig } from "../lib/config.mjs";
import { createBridge } from "../bridge.mjs";
import { createWebhookWire } from "../lib/webhook-wire.mjs";

const TOKEN = "TITKOS-webhook-token-123";
const msg = (o = {}) => ({ message_id: 7, date: 1700000000, chat: { id: -100, type: "group" },
  from: { id: 1, first_name: "J" }, text: "jóváhagyom", reply_to_message: { message_id: 3, from: { id: 99 } }, ...o });

function harness(onApprovalCandidate) {
  const delivered = [], cands = [];
  const h = createHandlers({
    groupId: "-100", allowIds: ["1"], requireMention: false, maxFileBytes: 1e6,
    bot: () => ({ username: "botty", id: 99 }), deliver: (l) => delivered.push(l),
    enqueueMedia: () => {}, logInbound: () => {},
    onApprovalCandidate: onApprovalCandidate || ((b) => { cands.push(b); }),
  });
  return { h, delivered, cands };
}

test("onApprovalCandidate a deliver ELOTT; dobasa -> 0 injektalas; a visszaadott kick a deliver UTAN", () => {
  const order = [];
  let fail = true;
  const { h, delivered } = harness(() => {
    order.push("persist");
    if (fail) throw new Error("write error x");
    return () => order.push("kick");
  });
  assert.throws(() => h.handleMessage(msg()), /write error/);
  assert.equal(delivered.length, 0);
  fail = false;
  const origPush = delivered.push.bind(delivered);
  delivered.push = (l) => { order.push("deliver"); return origPush(l); };
  h.handleMessage(msg());
  assert.deepEqual(order, ["persist", "persist", "deliver", "kick"]);
});

test("webhook-wire start(): idempotens — masodik hivas nem ad uj intervallumot", () => {
  const stateDir = tempDir("whw-");
  const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: stateDir, SUBETHA_REPLY_WEBHOOK: "https://h.example/x",
    SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN });
  const w = createWebhookWire(cfg, { post: async () => ({ ok: true }) });
  const orig = globalThis.setInterval;
  let n = 0;
  globalThis.setInterval = (...a) => { n++; return orig(...a); };
  try { w.start(); w.start(); } finally { globalThis.setInterval = orig; w.stop(); }
  assert.equal(n, 1);
});

test("onApprovalCandidate: allowlistes, reply_to-s, nem szerkesztett -> pontos torzs, deliver UTAN", () => {
  const { h, delivered, cands } = harness();
  h.handleMessage(msg());
  assert.equal(delivered.length, 1);
  assert.deepEqual(cands, [{ event_id: "-100:7", tg_from_id: "1", tg_chat_id: "-100", tg_message_id: 7,
    tg_reply_to: 3, tg_date: 1700000000, text: "jóváhagyom" }]);
});

test("onApprovalCandidate: a sajat csoport nem-allowlistes tagja is jelolt (a jogosultsag a szerveré)", () => {
  const { h, delivered, cands } = harness();
  h.handleMessage(msg({ from: { id: 2, first_name: "Anna" } }));
  assert.equal(delivered.length, 1);
  assert.equal(cands.length, 1);
  assert.equal(cands[0].tg_from_id, "2");
  assert.equal(cands[0].tg_chat_id, "-100");
});

test("onApprovalCandidate: idegen chat, bot, reply_to nelkul, szerkesztett -> 0", () => {
  const { h, delivered, cands } = harness();
  h.handleMessage(msg({ from: { id: 2 }, chat: { id: 2, type: "private" } })); // nem allowlistes DM: kapun kivul
  h.handleMessage(msg({ from: { id: 2 }, chat: { id: -555, type: "group" } })); // idegen csoport
  h.handleMessage(msg({ from: { id: 5, is_bot: true } }));
  assert.equal(delivered.length, 0, "a kapun kivuli uzenet nem jut be");
  h.handleMessage(msg({ reply_to_message: undefined }));
  h.handleMessage(msg(), { edited: true });
  assert.equal(delivered.length, 2, "a beinjektalas a webhooktol fuggetlen");
  assert.equal(cands.length, 0);
});

test("onApprovalCandidate: allowlistes DM reply-ja jelolt", () => {
  const { h, cands } = harness();
  h.handleMessage(msg({ chat: { id: 1, type: "private" } }));
  assert.equal(cands.length, 1);
});

function bridge(env = {}) {
  const stateDir = tempDir("whb-");
  const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100",
    TELEGRAM_ALLOWLIST_IDS: "1", TMUX_SESSION: `nincs-ilyen-${process.pid}`, BRIDGE_STATE_DIR: stateDir,
    BRIDGE_REQUIRE_MENTION: "false", ...env });
  const posts = [];
  const errs = [], outs = [];
  const oe = console.error, ol = console.log;
  console.error = (...a) => errs.push(a.join(" "));
  console.log = (...a) => outs.push(a.join(" "));
  try {
    const b = createBridge(cfg, { webhookPost: async (o) => { posts.push(o.body); return { ok: true, status: 200 }; } });
    return { b, cfg, stateDir, posts, errs, outs };
  } finally { console.error = oe; console.log = ol; }
}

test("createBridge: http:// webhook -> WEBHOOK KI sor stderr-en, health webhook=off, a hid fut", () => {
  const { b, cfg, errs, posts } = bridge({ SUBETHA_REPLY_WEBHOOK: "http://h.example/x?k=QSECRET",
    SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN });
  assert.ok(errs.some((l) => l.startsWith("[bridge] WEBHOOK KI: ")), errs.join("|"));
  assert.ok(!errs.join("").includes("QSECRET") && !errs.join("").includes(TOKEN));
  assert.equal(JSON.parse(readFileSync(cfg.healthFile, "utf8")).webhook, "off");
  b.processUpdate({ update_id: 1, message: msg() });
  assert.equal(b.delivery.depth(), 1);
  assert.equal(posts.length, 0);
  assert.equal(b.webhook.summary, "webhook=off");
});

test("createBridge: BE -> a jelolt a sorba megy es kimegy; token sehol a naplokban", async () => {
  const { b, cfg, stateDir, posts, outs, errs } = bridge({ SUBETHA_REPLY_WEBHOOK: "https://h.example/x?k=QSECRET",
    SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN });
  assert.equal(b.webhook.summary, "webhook=on host=h.example");
  b.processUpdate({ update_id: 1, message: msg() });
  await b.webhook.queue.tick();
  assert.deepEqual(posts.map((p) => p.event_id), ["-100:7"]);
  assert.equal(JSON.parse(readFileSync(cfg.healthFile, "utf8")).webhook, "on");
  const inbox = join(stateDir, "telegram-inbox");
  const files = readdirSync(inbox).filter((f) => f.startsWith("delivery-")).map((f) => readFileSync(join(inbox, f), "utf8"));
  const all = files.join("") + readFileSync(cfg.healthFile, "utf8") + readFileSync(cfg.webhookQueueFile, "utf8")
    + outs.join("") + errs.join("");
  assert.ok(!all.includes(TOKEN) && !all.includes("QSECRET"));
});

test("createBridge: sorfajl-iras hiba -> 0 injektalas, processUpdate DOB (offset nem lep); javitva 1 injektalas + 1 POST", async () => {
  const dir = tempDir("whq-");
  const blocker = join(dir, "blokk");
  writeFileSync(blocker, "fajl, nem konyvtar");
  const { b, posts } = bridge({ SUBETHA_REPLY_WEBHOOK: "https://h.example/x", SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN,
    BRIDGE_WEBHOOK_QUEUE_FILE: join(blocker, "webhook-queue.json") });
  const upd = { update_id: 1, message: msg() };
  assert.throws(() => b.processUpdate(upd), /write error/);
  assert.throws(() => b.processUpdate(upd), /write error/, "ujra-poll: ugyanaz, megint semmi");
  assert.equal(b.delivery.depth(), 0, "a sor-iras a beinjektalas ELOTT bukott: nincs duplikalt sor");
  rmSync(blocker);
  b.processUpdate(upd); // a kovetkezo getUpdates ugyanazt hozza — most sikerul
  await b.webhook.queue.tick();
  assert.equal(b.delivery.depth(), 1, "pontosan 1 injektalas");
  assert.deepEqual(posts.map((p) => p.event_id), ["-100:7"]);
  assert.ok(existsSync(join(blocker, "webhook-queue.json")));
});
