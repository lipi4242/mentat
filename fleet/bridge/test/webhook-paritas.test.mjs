// Paritas: a Partner-fork jovahagyo + ugy-uzenet aga (fixtura: fixtures/webhook-paritas.json,
// a fork lib/jovahagyas.mjs-ebol rogzitve) == a 2.0.1 tobbcelu webhookja ugyanazokra az update-ekre.
// Ugyanazok a vegpontok, sorrendben, BAJTRA ugyanazok a torzsek (_EVENT_ID=off,
// _TEXT=oneline:1500; a fixtura `rawBody` = a fork fetch-enek opts.body-ja) es fejlec-nevek,
// es ugyanazok a szalba irt valaszok.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "../lib/config.mjs";
import { createBridge } from "../bridge.mjs";
import { makeCert, startStub } from "./https-stub.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
const FX = JSON.parse(readFileSync(join(here, "fixtures", "webhook-paritas.json"), "utf8"));
const TOKEN = "TITKOS-paritas-token-1";
const TRANSPORT = new Set(["host", "connection", "content-length"]);
const noSsl = () => (makeCert() ? false : "openssl nincs");

async function fakeTelegram() {
  const sent = [];
  const srv = createServer((req, res) => {
    const u = new URL(req.url, "http://x");
    if (u.pathname.endsWith("/sendMessage")) {
      sent.push({ chat_id: u.searchParams.get("chat_id"),
        reply_to_message_id: Number(u.searchParams.get("reply_to_message_id")), text: u.searchParams.get("text") });
    }
    res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({ ok: true, result: { message_id: 9000 } }));
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  return { sent, url: `http://127.0.0.1:${srv.address().port}`, close: () => new Promise((r) => srv.close(r)) };
}

export function forkEnv(base) {
  const ugyLink = "https?://\\S*?/ugyek/([^\\s/?#]+)";
  return {
    SUBETHA_WEBHOOKS: "draft,ugy",
    SUBETHA_WEBHOOK_DRAFT_URL: `${base}/api/telegram/draft-approve`, SUBETHA_WEBHOOK_DRAFT_TOKEN: TOKEN,
    SUBETHA_WEBHOOK_DRAFT_TOKEN_HEADER: "X-Partner-Bridge-Token", SUBETHA_WEBHOOK_DRAFT_MATCH: "reply,reaction",
    SUBETHA_WEBHOOK_DRAFT_REPLY: "message", SUBETHA_WEBHOOK_DRAFT_REPLY_SKIP: "reason=no_anchor",
    SUBETHA_WEBHOOK_DRAFT_EVENT_ID: "off", SUBETHA_WEBHOOK_DRAFT_TEXT: "oneline:1500",
    SUBETHA_WEBHOOK_UGY_URL: `${base}/api/telegram/case-message`, SUBETHA_WEBHOOK_UGY_TOKEN: TOKEN,
    SUBETHA_WEBHOOK_UGY_TOKEN_HEADER: "X-Partner-Bridge-Token", SUBETHA_WEBHOOK_UGY_MATCH: "footer",
    SUBETHA_WEBHOOK_UGY_FROM: FX.kijelolt_kuldo,
    SUBETHA_WEBHOOK_UGY_EVENT_ID: "off", SUBETHA_WEBHOOK_UGY_TEXT: "oneline:1500",
    SUBETHA_WEBHOOK_UGY_FOOTER: `^Ügy:\\s+${ugyLink}/?$`, SUBETHA_WEBHOOK_UGY_FOOTER_ALL: ugyLink,
    SUBETHA_WEBHOOK_UGY_FOOTER_FIELD: "case_id", SUBETHA_WEBHOOK_UGY_FOOTER_EXCLUDE: "tipus", SUBETHA_WEBHOOK_UGY_UNLESS: "draft:ok=true",
    SUBETHA_WEBHOOK_UGY_REPLY: "message", SUBETHA_WEBHOOK_UGY_REPLY_SKIP: "ok=true",
    SUBETHA_WEBHOOK_UGY_NOFOOTER_REPLY: FX.nofooter_reply,
    SUBETHA_WEBHOOK_UGY_NOFOOTER_FILTER: join(here, "fixtures", "kerest-szuro.mjs"),
  };
}

// Egy forgatokonyv a 2.0.1 hidon: friss allapot, egy update, a sorok kiuritese.
export async function runCase(c, { env = forkEnv } = {}) {
  let responses = c.responses;
  const stub = await startStub((req, res) => {
    const v = responses[new URL(req.url, "https://x").pathname.split("/").pop()];
    if (!v) return res.writeHead(500).end();
    res.writeHead(v.status, { "content-type": "application/json" }).end(JSON.stringify(v.json));
  });
  const tgs = await fakeTelegram();
  const ol = console.log, oe = console.error;
  console.log = () => {}; console.error = () => {};
  try {
    const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: FX.group,
      TELEGRAM_ALLOWLIST_IDS: FX.allow.join(","), TMUX_SESSION: `nincs-ilyen-${process.pid}`,
      BRIDGE_STATE_DIR: tempDir("whp-"), BRIDGE_REQUIRE_MENTION: "false",
      SUBETHA_TELEGRAM_API: tgs.url, ...env(`https://127.0.0.1:${stub.port}`) });
    const b = createBridge(cfg, { webhookCa: stub.ca });
    Object.assign(b.botIdentity, FX.bot);
    b.processUpdate({ update_id: 1, ...c.update });
    await (b.webhook.drain ? b.webhook.drain() : b.webhook.queue?.tick()); // main-en nincs drain
    const requests = stub.requests.map((r) => ({ endpoint: r.url.split("/").pop(),
      headers: Object.keys(r.headers).filter((h) => !TRANSPORT.has(h)).sort(), body: JSON.parse(r.body) }));
    return { requests, replies: tgs.sent, raw: stub.requests };
  } finally {
    console.log = ol; console.error = oe;
    await stub.close(); await tgs.close();
  }
}

// Valodi Telegram-azonosito 7+ jegyu; a fixtura csak rovid, kitalalt id-kat hasznal.
// Az id-kulcsokat nezzuk (a 10 jegyu `date` idobelyeg legitim), a szovegekben is.
function longIds(o, key = "", out = []) {
  if (Array.isArray(o)) o.forEach((v) => longIds(v, key, out));
  else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) longIds(v, k, out);
  else if (typeof o === "number" && /(^|_)id$/i.test(key) && Math.abs(o) >= 1e6) out.push(key);
  else if (typeof o === "string") for (const m of o.matchAll(/"(\w*id)"\s*:\s*-?\d{7,}/gi)) out.push(m[1]);
  return out;
}

test("paritas-fixtura: token es valodi azonosito nincs benne", () => {
  assert.ok(!JSON.stringify(FX).includes("TOKEN"));
  assert.deepEqual(longIds(FX), []);
});

for (const c of FX.cases) {
  test(`paritas: ${c.name}`, { skip: noSsl() }, async () => {
    const got = await runCase(c);
    assert.deepEqual(got.requests.map((r) => r.endpoint), c.expected.requests.map((r) => r.endpoint), "vegpontok");
    got.requests.forEach((r, i) => {
      assert.equal(got.raw[i].body, c.expected.requests[i].rawBody, `nyers torzs ${r.endpoint}`);
      assert.deepEqual(r.headers, c.expected.requests[i].headers, `fejlec-nevek ${r.endpoint}`);
    });
    for (const r of got.raw) assert.equal(r.headers["x-partner-bridge-token"], TOKEN);
    assert.deepEqual(got.replies, c.expected.replies, "szalba irt valaszok");
  });
}
