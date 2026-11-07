// Tobb nevesitett webhook-cel: env-szerzodes, egyuttelés a `default` cellal,
// sorrend (_UNLESS) kimerult fuggoseg utan, fail-closed szuro, notice `target`.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseWebhookTargets } from "../lib/webhook-targets.mjs";
import { loadConfig } from "../lib/config.mjs";
import { createWebhookWire } from "../lib/webhook-wire.mjs";
import { RETRY_DELAYS_MS } from "../lib/webhook-queue.mjs";

const TOKEN = "TITKOS-celok-token-9";
const env = (o = {}) => ({ SUBETHA_WEBHOOKS: "a", SUBETHA_WEBHOOK_A_URL: "https://h.example/a?k=QSECRET",
  SUBETHA_WEBHOOK_A_TOKEN: TOKEN, ...o });

test("celok: hibas beallitas -> KI okkal, a reason-ben se token, se URL; a tobbi cel el", () => {
  const bad = [
    [{ SUBETHA_WEBHOOK_A_URL: "http://h.example/a?k=QSECRET" }, /https/],
    [{ SUBETHA_WEBHOOK_A_TOKEN: "" }, /TOKEN hianyzik/],
    [{ SUBETHA_WEBHOOK_A_MATCH: "reply,barmi" }, /MATCH ismeretlen/],
    [{ SUBETHA_WEBHOOK_A_MATCH: "footer" }, /FOOTER kell/],
    [{ SUBETHA_WEBHOOK_A_MATCH: "footer", SUBETHA_WEBHOOK_A_FOOTER: "(" }, /nem ervenyes regex/],
    [{ SUBETHA_WEBHOOK_A_UNLESS: "b:ok=true" }, /nem korabbi/],
    [{ SUBETHA_WEBHOOK_A_TOKEN_HEADER: "X Rossz" }, /TOKEN_HEADER/],
    [{ SUBETHA_WEBHOOK_A_REPLY_TO: "igen" }, /REPLY_TO csak on\|off/],
    [{ SUBETHA_WEBHOOK_A_REPLY: "message", SUBETHA_WEBHOOK_A_REPLY_SKIP: "csakkulcs" }, /REPLY_SKIP/],
  ];
  for (const [o, re] of bad) {
    const [t] = parseWebhookTargets(env(o));
    assert.equal(t.enabled, false, JSON.stringify(o));
    assert.match(t.reason, re);
    assert.ok(!t.reason.includes(TOKEN) && !t.reason.includes("QSECRET"));
  }
  const ts = parseWebhookTargets(env({ SUBETHA_WEBHOOKS: "a,default,a,b", SUBETHA_WEBHOOK_B_URL: "https://h.example/b",
    SUBETHA_WEBHOOK_B_TOKEN: TOKEN, SUBETHA_WEBHOOK_B_UNLESS: "a:ok=true" }));
  assert.deepEqual(ts.map((t) => [t.name, t.enabled]), [["a", true], ["default", false], ["a", false], ["b", true]]);
  assert.deepEqual(ts[3].unless, { target: "a", key: "ok", value: "true", raw: "a:ok=true" });
});

function wire(e, post) {
  const stateDir = tempDir("whc-");
  const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: stateDir, ...e });
  const replies = [], warns = [], clock = { t: 1_000_000 };
  const w = createWebhookWire(cfg, { post, warn: (s) => warns.push(s), now: () => clock.t,
    sendReply: async (r) => { replies.push(r); } });
  return { w, cfg, replies, warns, clock, inbox: join(stateDir, "telegram-inbox") };
}
const body = (id = 7) => ({ event_id: `-100:${id}`, tg_from_id: "1", tg_chat_id: "-100", tg_message_id: id,
  tg_reply_to: 3, tg_date: 1700000000, text: "ok" });
const notices = (dir) => readdirSync(dir).flatMap((f) => readFileSync(join(dir, f), "utf8").trim().split("\n"))
  .map((l) => JSON.parse(l)).filter((r) => r.type === "notice");

test("celok: default + nevesitett egyutt — a default torzse es notice-a valtozatlan, a nevesitetten target", async () => {
  const posts = [];
  const { w, cfg, inbox } = wire({ SUBETHA_REPLY_WEBHOOK: "https://d.example/x", SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN,
    ...env({ SUBETHA_WEBHOOK_A_MATCH: "reply,reaction" }) },
  async (o) => { posts.push([o.url, o.header, o.body]); return { ok: true, status: 200 }; });
  assert.equal(w.summary, "webhook=on targets=default@d.example,a@h.example");
  w.onApprovalCandidate(body())();
  w.onApprovalCandidate({ ...body(8), event_id: "-100:8:r1:1700000001" }, { kind: "reaction" })();
  await w.drain();
  assert.deepEqual(posts.map((p) => [new URL(p[0]).host, p[1], p[2].event_id]), [
    ["d.example", "X-Bridge-Token", "-100:7"], ["h.example", "X-Bridge-Token", "-100:7"],
    ["h.example", "X-Bridge-Token", "-100:8:r1:1700000001"]]);
  assert.ok(existsSync(cfg.webhookQueueFile) && existsSync(join(cfg.stateDir, "telegram-state", "webhook-queue-a.json")));
  const ok = notices(inbox).filter((r) => r.event === "webhook_ok");
  assert.deepEqual(ok.map((r) => r.target ?? null).sort(), ["a", "a", null]);
});

test("celok: a fuggoseg halozati kimerulese utan a fuggo cel is hiv (mint a forkban), a szal nema", async () => {
  const calls = [];
  const { w, replies, inbox, clock } = wire(env({ SUBETHA_WEBHOOKS: "a,b", SUBETHA_WEBHOOK_A_REPLY: "message",
    SUBETHA_WEBHOOK_B_URL: "https://h.example/b", SUBETHA_WEBHOOK_B_TOKEN: TOKEN, SUBETHA_WEBHOOK_B_UNLESS: "a:ok=true" }),
  async (o) => { calls.push(o.url.includes("/b") ? "b" : "a");
    return o.url.includes("/b") ? { ok: true, status: 200 } : { ok: false, error: "ECONNREFUSED" }; });
  w.onApprovalCandidate(body())();
  await w.drain();
  assert.deepEqual(calls, ["a"], "b var a-ra");
  for (let i = 0; i < RETRY_DELAYS_MS.length; i++) { clock.t += 300_000; await w.drain(); await w.drain(); }
  assert.deepEqual(calls, ["a", "a", "a", "a", "b"]);
  assert.deepEqual(replies, []);
  assert.ok(notices(inbox).some((r) => r.event === "webhook_failed" && r.target === "a"));
});

test("celok: hibas NOFOOTER_FILTER -> fail-closed, nincs visszakerdezes, nincs POST", async () => {
  const posts = [];
  const { w, replies } = wire(env({ SUBETHA_WEBHOOK_A_MATCH: "footer", SUBETHA_WEBHOOK_A_FOOTER: "^Ref: (\\S+)$",
    SUBETHA_WEBHOOK_A_NOFOOTER_REPLY: "Melyikre?", SUBETHA_WEBHOOK_A_NOFOOTER_FILTER: "/nincs/ilyen/szuro.mjs" }),
  async (o) => { posts.push(o); return { ok: true, status: 200 }; });
  w.onApprovalCandidate(body(), { kind: "message", replyToFromId: 99, botId: 99, replyToText: "lablec nelkul" })();
  await w.drain();
  assert.equal(posts.length, 0);
  assert.deepEqual(replies, []);
});

test("celok: footer-cel a bot uzenetere — id a lablecbol, tg_reply_to nelkul; idegen uzenetre semmi", async () => {
  const posts = [];
  const { w } = wire(env({ SUBETHA_WEBHOOK_A_MATCH: "footer", SUBETHA_WEBHOOK_A_FOOTER: "^Ref: (\\S+)$",
    SUBETHA_WEBHOOK_A_FOOTER_FIELD: "ref_id" }), async (o) => { posts.push(o.body); return { ok: true, status: 200 }; });
  assert.equal(w.onApprovalCandidate(body(), { kind: "message", replyToFromId: 5, botId: 99, replyToText: "x\nRef: r%2D1" }), undefined);
  w.onApprovalCandidate(body(), { kind: "message", replyToFromId: 99, botId: 99, replyToText: "x\nRef: r%2D1" })();
  await w.drain();
  assert.deepEqual(posts, [{ event_id: "-100:7", tg_from_id: "1", tg_chat_id: "-100", tg_message_id: 7,
    tg_date: 1700000000, text: "ok", ref_id: "r-1" }]);
});


test("celok: footer-cel _REPLY_TO=on — a torzs viszi a tg_reply_to-t (a horgonyt), a tg_message_id utan", async () => {
  const posts = [];
  const { w } = wire(env({ SUBETHA_WEBHOOK_A_MATCH: "footer", SUBETHA_WEBHOOK_A_FOOTER: "^Ref: (\\S+)$",
    SUBETHA_WEBHOOK_A_FOOTER_FIELD: "case_id", SUBETHA_WEBHOOK_A_REPLY_TO: "on" }),
  async (o) => { posts.push(o.body); return { ok: true, status: 200 }; });
  w.onApprovalCandidate(body(), { kind: "message", replyToFromId: 99, botId: 99, replyToText: "Opciok\nRef: u-42" })();
  await w.drain();
  assert.deepEqual(posts, [{ event_id: "-100:7", tg_from_id: "1", tg_chat_id: "-100", tg_message_id: 7,
    tg_reply_to: 3, tg_date: 1700000000, case_id: "u-42", text: "ok" }]);
  assert.deepEqual(Object.keys(posts[0]), ["event_id", "tg_from_id", "tg_chat_id", "tg_message_id", "tg_reply_to",
    "tg_date", "case_id", "text"]);
});
