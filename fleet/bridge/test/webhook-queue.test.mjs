// 3.1 jovahagyo webhook: tartos sor (ujraprobak, dedup, ujrainditas, notice).
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createWebhookQueue, RETRY_DELAYS_MS } from "../lib/webhook-queue.mjs";
import { readDay } from "../lib/delivery-log.mjs";
import { makeCert, startStub, closedPort } from "./https-stub.mjs";

const TOKEN = "TITKOS-webhook-token-123";
const body = (id = 7) => ({ event_id: `-100:${id}`, tg_from_id: "1", tg_chat_id: "-100",
  tg_message_id: id, tg_reply_to: 3, tg_date: 1700000000, text: "ok" });
const today = () => new Date().toISOString().slice(0, 10);
const noSsl = () => (makeCert() ? false : "openssl nincs");

function setup(over = {}) {
  const dir = tempDir("whq-");
  const clock = { t: 1_000_000 };
  const logs = [];
  const make = (o = {}) => createWebhookQueue({ file: join(dir, "webhook-queue.json"),
    cfg: { url: o.url ?? over.url, token: TOKEN }, logDir: join(dir, "inbox"),
    log: (...a) => logs.push(a.join(" ")), now: () => clock.t, ca: over.ca, ...o.extra });
  return { dir, clock, logs, make, file: join(dir, "webhook-queue.json") };
}

test("RETRY_DELAYS_MS = 10 s, 60 s, 300 s", () => {
  assert.deepEqual(RETRY_DELAYS_MS, [10_000, 60_000, 300_000]);
});

test("https-stub EGYSZER kapja, helyes event_id-vel; masodik enqueue no-op", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(200).end());
  try {
    const s = setup({ url: stub.url, ca: stub.ca });
    const q = s.make();
    await q.enqueue(body());
    await q.enqueue(body());
    await q.tick();
    assert.equal(stub.requests.length, 1);
    assert.equal(JSON.parse(stub.requests[0].body).event_id, "-100:7");
    assert.equal(q.depth(), 0);
    // ujrainditas utan is emlekszik (done-halmaz a fajlban)
    await s.make().enqueue(body());
    assert.equal(stub.requests.length, 1);
  } finally { await stub.close(); }
});

test("zart port: 10/60/300 s utan ujra, 4 proba, majd webhook_failed notice; ujrainditas utan folytatodik", async () => {
  const port = await closedPort();
  const s = setup({ url: `https://127.0.0.1:${port}/hook?k=QSECRET` });
  let calls = 0;
  const { postWebhook } = await import("../lib/webhook.mjs");
  const post = (o) => { calls++; return postWebhook(o); };
  let q = s.make({ extra: { post } });
  await q.enqueue(body());
  assert.equal(calls, 1);
  s.clock.t += 9_999; await q.tick(); assert.equal(calls, 1, "10 s elott nem probal");
  s.clock.t += 1; await q.tick(); assert.equal(calls, 2);
  // ujrainditas: uj sor ugyanazzal a fajllal
  q = s.make({ extra: { post } });
  assert.equal(q.depth(), 1);
  s.clock.t += 59_999; await q.tick(); assert.equal(calls, 2);
  s.clock.t += 1; await q.tick(); assert.equal(calls, 3);
  s.clock.t += 300_000; await q.tick(); assert.equal(calls, 4);
  assert.equal(q.depth(), 0);
  s.clock.t += 1_000_000; await q.tick(); assert.equal(calls, 4, "osszesen 4 proba");
  // visszajatszas (ujrainditas utan is): a kimerult elem a done-ban -> nincs uj 4-es kor
  await q.enqueue(body());
  await s.make({ extra: { post } }).enqueue(body());
  assert.equal(calls, 4, "a kimerult event_id ujra-enqueue-ja no-op");
  const notices = readDay(join(s.dir, "inbox"), today()).filter((r) => r.type === "notice");
  assert.equal(notices.length, 1);
  assert.equal(notices[0].event, "webhook_failed");
  assert.equal(notices[0].chat_id, "-100");
  assert.equal(notices[0].msg_id, 7);
  // a token es a query sehol
  const all = readFileSync(join(s.dir, "inbox", `delivery-${today()}.jsonl`), "utf8")
    + readFileSync(s.file, "utf8") + s.logs.join("\n");
  assert.ok(!all.includes(TOKEN) && !all.includes("QSECRET"));
});

test("a sorfajl a torzset tartja, a tokent nem; hibamezo tokenmentes", async () => {
  const s = setup({ url: "https://127.0.0.1:1/hook" });
  const q = s.make({ extra: { post: async () => ({ ok: false, error: "ECONNREFUSED" }) } });
  await q.enqueue(body());
  const raw = readFileSync(s.file, "utf8");
  assert.ok(raw.includes("-100:7"));
  assert.ok(!raw.includes(TOKEN));
  assert.equal(JSON.parse(raw).items[0].last_error, "ECONNREFUSED");
});

test("enqueue STRIKT: irhatatlan sorfajl -> dob (az offset igy nem lep)", () => {
  const dir = tempDir("whq-");
  writeFileSync(join(dir, "fajl"), "x");
  const q = createWebhookQueue({ file: join(dir, "fajl", "q.json"), cfg: { url: "https://x/", token: TOKEN },
    logDir: dir, post: async () => ({ ok: true }) });
  assert.throws(() => q.enqueue(body()), /write error/);
  assert.equal(q.depth(), 0, "a sikertelen iras nem marad a memoriaban sem");
});

test("tick: egyszerre egy futas; a busy finally-ben szabadul (dobo post utan is)", async () => {
  const s = setup({ url: "https://x/" });
  let calls = 0, release;
  const post = () => { calls++; if (calls === 1) return new Promise((r) => { release = r; }); throw new Error("bumm"); };
  const q = s.make({ extra: { post } });
  const p1 = q.enqueue(body(1));
  q.enqueue(body(2)); // busy alatt: nem indit masodik parhuzamos kort
  assert.equal(calls, 1);
  release({ ok: true });
  await p1;
  assert.equal(calls, 2, "a busy alatt erkezett elem a kor vegen sorra kerul");
  s.clock.t += 10_000;
  await q.tick();
  assert.equal(calls, 3, "a dobo post utan is van kovetkezo kor");
});

const notices = (s) => readDay(join(s.dir, "inbox"), today()).filter((r) => r.type === "notice");

test("2xx: webhook_ok notice HTTP statusszal, chat_id/msg_id a torzsbol", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(200).end());
  try {
    const s = setup({ url: stub.url, ca: stub.ca });
    await s.make().enqueue(body());
    assert.equal(stub.requests.length, 1);
    const n = notices(s).filter((r) => r.event === "webhook_ok");
    assert.equal(n.length, 1);
    assert.equal(n[0].detail, "HTTP 200");
    assert.equal(n[0].chat_id, "-100");
    assert.equal(n[0].msg_id, 7);
    assert.ok(!JSON.stringify(n).includes(TOKEN));
  } finally { await stub.close(); }
});

test("403: veglegesen elutasitva, EGY POST, webhook_rejected, akkor is ha az ora 10 percet lep", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => res.writeHead(403).end());
  try {
    const s = setup({ url: stub.url, ca: stub.ca });
    const q = s.make();
    await q.enqueue(body());
    s.clock.t += 600_000; await q.tick();
    assert.equal(stub.requests.length, 1);
    assert.equal(q.depth(), 0);
    const n = notices(s);
    assert.equal(n.filter((r) => r.event === "webhook_rejected").length, 1);
    assert.equal(n.find((r) => r.event === "webhook_rejected").detail, "HTTP 403");
    assert.equal(n.find((r) => r.event === "webhook_rejected").chat_id, "-100");
    assert.equal(n.find((r) => r.event === "webhook_rejected").msg_id, 7);
    assert.equal(n.filter((r) => r.event === "webhook_failed").length, 0);
    await s.make().enqueue(body()); // done-ban: nincs ujabb POST
    assert.equal(stub.requests.length, 1);
  } finally { await stub.close(); }
});

test("429 es 408: a regi ujraprobas viselkedes marad", { skip: noSsl() }, async () => {
  for (const code of [429, 408]) {
    const stub = await startStub((req, res) => res.writeHead(code).end());
    try {
      const s = setup({ url: stub.url, ca: stub.ca });
      const q = s.make();
      await q.enqueue(body());
      assert.equal(q.depth(), 1);
      s.clock.t += 10_000; await q.tick();
      assert.equal(stub.requests.length, 2, `HTTP ${code} ujra probal`);
      assert.equal(notices(s).filter((r) => r.event === "webhook_rejected").length, 0);
    } finally { await stub.close(); }
  }
});

test("a harom webhook-notice sora azonos kulcshalmaz, azonos chat_id/msg_id", { skip: noSsl() }, async () => {
  const keys = [];
  for (const [code, event] of [[200, "webhook_ok"], [403, "webhook_rejected"]]) {
    const stub = await startStub((req, res) => res.writeHead(code).end());
    try {
      const s = setup({ url: stub.url, ca: stub.ca });
      await s.make().enqueue(body());
      keys.push([event, notices(s).find((r) => r.event === event)]);
    } finally { await stub.close(); }
  }
  const s = setup({ url: "https://x/" });
  const q = s.make({ extra: { post: async () => ({ ok: false, error: "ECONNREFUSED" }) } });
  await q.enqueue(body());
  for (let i = 0; i < RETRY_DELAYS_MS.length; i++) { s.clock.t += 300_000; await q.tick(); }
  keys.push(["webhook_failed", notices(s).find((r) => r.event === "webhook_failed")]);
  const shape = (r) => Object.keys(r).sort().join(",");
  for (const [event, row] of keys) {
    assert.ok(row, `${event} sor hianyzik`);
    assert.equal(shape(row), "chat_id,detail,event,id,msg_id,ts,type,v", event);
    assert.equal(row.chat_id, "-100", event);
    assert.equal(row.msg_id, 7, event);
  }
});
