// _UNLESS-sorrend a review forgatokonyveire (szulo-kimenet a sorfajlbol, fail-closed),
// egy szulo = egy fuggo, es a valasz-meret bajtban (overflow).
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseWebhookTargets } from "../lib/webhook-targets.mjs";
import { loadConfig } from "../lib/config.mjs";
import { createWebhookWire } from "../lib/webhook-wire.mjs";
import { postWebhook } from "../lib/webhook.mjs";
import { makeCert, startStub } from "./https-stub.mjs";

const TOKEN = "TITKOS-celok-token-9";
const env = (o = {}) => ({ SUBETHA_WEBHOOKS: "a", SUBETHA_WEBHOOK_A_URL: "https://h.example/a?k=QSECRET",
  SUBETHA_WEBHOOK_A_TOKEN: TOKEN, ...o });
const body = (id = 7) => ({ event_id: `-100:${id}`, tg_from_id: "1", tg_chat_id: "-100", tg_message_id: id,
  tg_reply_to: 3, tg_date: 1700000000, text: "ok" });
const notices = (dir) => readdirSync(dir).flatMap((f) => readFileSync(join(dir, f), "utf8").trim().split("\n"))
  .map((l) => JSON.parse(l)).filter((r) => r.type === "notice");

// draft + ugy (footer, _UNLESS=draft:ok=true) — a review forgatokonyvei
const chainEnv = (o = {}) => env({ SUBETHA_WEBHOOKS: "a,b", SUBETHA_WEBHOOK_A_REPLY: "message",
  SUBETHA_WEBHOOK_B_URL: "https://h.example/b", SUBETHA_WEBHOOK_B_TOKEN: TOKEN, SUBETHA_WEBHOOK_B_MATCH: "footer",
  SUBETHA_WEBHOOK_B_FOOTER: "^Ref: (\\S+)$", SUBETHA_WEBHOOK_B_UNLESS: "a:ok=true", ...o });
const footCtx = { kind: "message", replyToFromId: 99, botId: 99, replyToText: "x\nRef: r1" };

test("UNLESS-res: a draft mar lefutott (ok:true), a b-sor irasa csak az ujrajatszaskor sikerul -> b NEM hiv", async () => {
  const posts = [];
  const { w, cfg, replies, inbox } = (() => {
    const stateDir = tempDir("whc-");
    const e = { TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "1",
      TMUX_SESSION: "s", BRIDGE_STATE_DIR: stateDir, ...chainEnv() };
    const c = loadConfig(e), rep = [];
    return { cfg: c, replies: rep, inbox: join(stateDir, "telegram-inbox"),
      w: createWebhookWire(c, { warn: () => {}, sendReply: async (x) => { rep.push(x); },
        post: async (o) => { posts.push(o.url); return { ok: true, status: 200, json: { ok: true, message: "Kesz." } }; } }) };
  })();
  mkdirSync(join(cfg.stateDir, "telegram-state", "webhook-queue-b.json"), { recursive: true }); // irhatatlan b-sor
  assert.throws(() => w.onApprovalCandidate(body(), footCtx));
  await w.drain();
  assert.deepEqual(posts, ["https://h.example/a?k=QSECRET"]);
  rmSync(join(cfg.stateDir, "telegram-state", "webhook-queue-b.json"), { recursive: true });
  w.onApprovalCandidate(body(), footCtx)(); // ujrajatszas: a mar kesz, a b uj
  await w.drain();
  assert.deepEqual(posts, ["https://h.example/a?k=QSECRET"], "b nem hivhat: a szulo ok:true volt");
  assert.deepEqual(replies.map((r) => r.text), ["Kesz."], "egy valasz, duplikatum nelkul");
  assert.ok(notices(inbox).some((r) => r.event === "webhook_skipped" && r.target === "b"));
});

test("UNLESS: a szulo kesz, de a kimenete ismeretlen -> fail-closed skip, naplozva", async () => {
  const posts = [];
  const stateDir = tempDir("whc-");
  mkdirSync(join(stateDir, "telegram-state"), { recursive: true });
  writeFileSync(join(stateDir, "telegram-state", "webhook-queue-a.json"), JSON.stringify({ items: [], done: ["-100:7"] }));
  const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: stateDir, ...chainEnv() });
  const w = createWebhookWire(cfg, { warn: () => {}, sendReply: async () => {},
    post: async (o) => { posts.push(o.url); return { ok: true, status: 200 }; } });
  w.onApprovalCandidate(body(), footCtx)();
  await w.drain();
  assert.deepEqual(posts, []);
  const sk = notices(join(stateDir, "telegram-inbox")).find((r) => r.event === "webhook_skipped");
  assert.equal(sk.target, "b");
  assert.match(sk.detail, /ismeretlen/);
});

test("egy szulore csak EGY _UNLESS-fuggo (egy lanc = legfeljebb egy szal-valasz)", () => {
  const ts = parseWebhookTargets(chainEnv({ SUBETHA_WEBHOOKS: "a,b,c", SUBETHA_WEBHOOK_C_URL: "https://h.example/c",
    SUBETHA_WEBHOOK_C_TOKEN: TOKEN, SUBETHA_WEBHOOK_C_UNLESS: "a:ok=true" }));
  assert.deepEqual(ts.map((t) => [t.name, t.enabled]), [["a", true], ["b", true], ["c", false]]);
  assert.match(ts[2].reason, /mar van fuggoje/);
});

test("valasz-meret bajtban: 64 KB folott overflow, nincs parse, a kapcsolat bontva", { skip: makeCert() ? false : "openssl nincs" }, async () => {
  const big = JSON.stringify({ message: "é".repeat(40_000) }); // 40k karakter, ~80 KB
  const stub = await startStub((req, res) => res.writeHead(200, { "content-type": "application/json" }).end(big));
  try {
    const r = await postWebhook({ url: stub.url, token: TOKEN, body: { a: 1 }, ca: stub.ca });
    assert.equal(r.ok, true);
    assert.equal(r.overflow, true);
    assert.equal(r.json, undefined);
    const small = await startStub((req, res) => res.writeHead(200).end(JSON.stringify({ message: "é".repeat(30_000) })));
    try {
      const r2 = await postWebhook({ url: small.url, token: TOKEN, body: { a: 1 }, ca: small.ca });
      assert.equal(r2.overflow, undefined, "30k karakter ~60 KB: belefer");
      assert.equal(r2.json.message.length, 30_000);
    } finally { await small.close(); }
  } finally { await stub.close(); }
});
