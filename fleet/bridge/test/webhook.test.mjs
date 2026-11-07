// 3.1 jovahagyo webhook: config-ertelmezes es az EGY https-POST (postWebhook).
import test from "node:test";
import assert from "node:assert/strict";
import { parseWebhookConfig } from "../lib/webhook-config.mjs";
import { postWebhook, DEFAULT_TIMEOUT_MS } from "../lib/webhook.mjs";
import { makeCert, startStub, closedPort } from "./https-stub.mjs";

const TOKEN = "TITKOS-webhook-token-123";
const BODY = { event_id: "-100:7", tg_from_id: "1", tg_chat_id: "-100", tg_message_id: 7,
  tg_reply_to: 3, tg_date: 1700000000, text: "jóváhagyom" };
const noSsl = () => (makeCert() ? false : "openssl nincs");

test("parseWebhookConfig: URL nelkul csendesen KI", () => {
  assert.deepEqual(parseWebhookConfig({}), { enabled: false, reason: null });
  assert.deepEqual(parseWebhookConfig({ SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN }), { enabled: false, reason: null });
});

test("parseWebhookConfig: nem https / token nelkul / ervenytelen -> KI okkal, titok nelkul", () => {
  const cases = [
    { SUBETHA_REPLY_WEBHOOK: "http://h.example/x?k=QSECRET", SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN },
    { SUBETHA_REPLY_WEBHOOK: "https://h.example/x?k=QSECRET" },
    { SUBETHA_REPLY_WEBHOOK: "nem url QSECRET", SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN },
  ];
  for (const env of cases) {
    const c = parseWebhookConfig(env);
    assert.equal(c.enabled, false);
    assert.equal(typeof c.reason, "string");
    assert.ok(!c.reason.includes(TOKEN) && !c.reason.includes("QSECRET"), c.reason);
  }
  assert.match(parseWebhookConfig(cases[0]).reason, /https/);
  assert.match(parseWebhookConfig(cases[1]).reason, /TOKEN/);
});

test("parseWebhookConfig: https + token -> BE, host query nelkul", () => {
  const c = parseWebhookConfig({ SUBETHA_REPLY_WEBHOOK: "https://h.example:8443/x?k=1",
    SUBETHA_REPLY_WEBHOOK_TOKEN: TOKEN });
  assert.equal(c.enabled, true);
  assert.equal(c.host, "h.example:8443");
  assert.equal(c.token, TOKEN);
});

test("postWebhook: pontos torzs es fejlecek, egyszer", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(200).end("ok"));
  try {
    const r = await postWebhook({ url: stub.url, token: TOKEN, body: BODY, ca: stub.ca });
    assert.deepEqual(r, { ok: true, status: 200 });
    assert.equal(stub.requests.length, 1);
    const q = stub.requests[0];
    assert.equal(q.method, "POST");
    assert.equal(q.headers["x-bridge-token"], TOKEN);
    assert.equal(q.headers["content-type"], "application/json");
    const got = JSON.parse(q.body);
    assert.deepEqual(Object.keys(got).sort(), ["event_id", "text", "tg_chat_id", "tg_date",
      "tg_from_id", "tg_message_id", "tg_reply_to"]);
    assert.deepEqual(got, BODY);
  } finally { await stub.close(); }
});

test("postWebhook: ismeretlen CA -> hiba (rejectUnauthorized)", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(200).end());
  try {
    const r = await postWebhook({ url: stub.url, token: TOKEN, body: BODY });
    assert.equal(r.ok, false);
    assert.equal(stub.requests.length, 0);
  } finally { await stub.close(); }
});

test("postWebhook: 302 -> nem koveti, hiba", { skip: noSsl() }, async () => {
  const target = await startStub((req, res) => res.writeHead(200).end());
  const redir = await startStub((req, res) => res.writeHead(302, { location: target.url }).end());
  try {
    const r = await postWebhook({ url: redir.url, token: TOKEN, body: BODY, ca: redir.ca });
    assert.equal(r.ok, false);
    assert.equal(r.status, 302);
    assert.match(r.error, /atiranyitas/);
    assert.equal(target.requests.length, 0);
  } finally { await redir.close(); await target.close(); }
});

test("postWebhook: 500 -> hiba, a hibaszoveg tokent nem visel", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(500).end(TOKEN));
  try {
    const r = await postWebhook({ url: stub.url, token: TOKEN, body: BODY, ca: stub.ca });
    assert.equal(r.ok, false);
    assert.ok(!JSON.stringify(r).includes(TOKEN));
  } finally { await stub.close(); }
});

test("postWebhook: zart port -> hiba, nem dob", async () => {
  const port = await closedPort();
  const r = await postWebhook({ url: `https://127.0.0.1:${port}/hook`, token: TOKEN, body: BODY });
  assert.equal(r.ok, false);
  assert.match(r.error, /ECONNREFUSED/);
});

test("postWebhook: alapertelmezett idokorlat 5 s", () => {
  assert.equal(DEFAULT_TIMEOUT_MS, 5000);
});

test("postWebhook: nem valaszolo stub -> timeout", { skip: noSsl() }, async () => {
  const stub = await startStub(() => { /* sosem valaszol */ });
  try {
    const t0 = Date.now();
    const r = await postWebhook({ url: stub.url, token: TOKEN, body: BODY, ca: stub.ca, timeoutMs: 300 });
    assert.equal(r.ok, false);
    assert.match(r.error, /timeout/);
    assert.ok(Date.now() - t0 < 3000);
  } finally { await stub.close(); }
});

test("postWebhook: csepegtetett valasz -> a fali oras korlat vagja el", { skip: noSsl() }, async () => {
  // A socket-idle timeout itt sosem sul el: 100 ms-enkent jon egy bajt.
  const timers = [];
  const stub = await startStub((req, res) => {
    res.writeHead(200);
    timers.push(setInterval(() => res.write("."), 100));
  });
  try {
    const t0 = Date.now();
    // A teszt maga ne lógjon, ha a korlát hiányzik: 3 s-os versenytárs.
    let guard;
    const r = await Promise.race([
      postWebhook({ url: stub.url, token: TOKEN, body: BODY, ca: stub.ca, timeoutMs: 400 }),
      new Promise((res) => { guard = setTimeout(() => res({ ok: "LOG", error: "nincs fali oras korlat" }), 3000); }),
    ]);
    clearTimeout(guard);
    assert.equal(r.ok, false, r.error);
    assert.match(r.error, /timeout/);
    assert.ok(Date.now() - t0 < 3000, `${Date.now() - t0} ms`);
  } finally { timers.forEach(clearInterval); await stub.close(); }
});
